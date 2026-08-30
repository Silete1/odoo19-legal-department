# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Handing an accreditation dossier to the officer who asked for it.

One route, and it is as narrow as it can be made:

* ``auth='user'`` - never public. An accreditation dossier is the complete
  evidence file of a private company and has no business being reachable
  without a session.
* the route takes the *request*, never a list of attachment ids, so a caller
  cannot ask for somebody else's evidence by guessing numbers;
* the reader is checked against the request itself before a single byte is
  read, and every attachment is checked again on the way into the archive;
* the archive is built on demand and never stored, so the dossier costs no
  second copy of anything and cannot go stale.

The route converter deliberately does *not* check access - it only browses the
id - so the explicit ``check_access`` below is what stands between a curious
internal user and another department's file.
"""
import logging

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import content_disposition, request
from odoo.tools import osutil

_logger = logging.getLogger(__name__)


class DmaAccreditationDossier(http.Controller):

    @http.route(
        "/dma/accreditation/dossier/<model('dma.accreditation.request'):accreditation>",
        type="http", auth="user", methods=["GET"],
    )
    def download_dossier(self, accreditation, **kwargs):
        """Return the complete evidence file of one accreditation as a ZIP."""
        accreditation = accreditation.exists()
        if not accreditation:
            return request.not_found()
        try:
            # The gate. Everything downstream derives its file list from this
            # record, so passing here is what makes the archive this reader's
            # to have.
            accreditation.check_access("read")
            content = accreditation._dossier_zip_bytes()
        except (AccessError, MissingError):
            # Deliberately indistinguishable from "no such file": whether a
            # given accreditation exists is itself information.
            return request.not_found()
        except UserError as error:
            _logger.info(
                "DMA dossier refused for %s: %s", accreditation.display_name, error,
            )
            return request.make_response(
                str(error),
                headers=[
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("X-Content-Type-Options", "nosniff"),
                ],
                status=400,
            )

        filename = osutil.clean_filename("%s_dossier.zip" % accreditation._dossier_filename())
        return request.make_response(content, headers=[
            ("Content-Type", "application/zip"),
            ("Content-Length", len(content)),
            # RFC 6266, percent encoded: the only correct way to put a file
            # name a user chose into a header.
            ("Content-Disposition", content_disposition(filename)),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'none'"),
            ("Cache-Control", "private, no-store"),
        ])
