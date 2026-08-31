# i18n seed - custom_addons/legal_procedure

English msgid (as now in source) | Arabic that was stripped (translators reuse as msgstr seed) | file.

| English msgid | Arabic seed | File |
|---|---|---|
| Not Required | غير مطلوب | models/legal_constants.py |
| Not Provided | لم يُقدَّم | models/legal_constants.py |
| Provided | مُقدَّم | models/legal_constants.py |
| Under Review | قيد التدقيق | models/legal_constants.py |
| Accepted | مقبول | models/legal_constants.py |
| Rejected | مرفوض | models/legal_constants.py |
| Expired | منتهي الصلاحية | models/legal_constants.py |
| Subject | الموضوع (على الكتاب الرسمي تُكتب: م/ الموضوع) | models/legal_case.py |
| The power of attorney the runner is presenting. The counter checks the name on it against the card in their hand, so a file with the wrong one is a wasted morning. | الوكالة | models/legal_case.py |
| The Power Of Attorney Is | الوكالة | models/legal_case.py |
| No power of attorney is attached, and %s will not deal with anybody who is not named on one. | وكالة | models/legal_case.py |
| The file this entry belongs to. Empty for a letter that arrived before anybody opened a file for it - which is most of the interesting post. | المعاملة | models/legal_correspondence.py |
| The default official letter this procedure sends. A step may override it where the walk writes to more than one body. | كتاب رسمي | models/legal_correspondence.py |
| The row number on the letter's numbered list. It is quoted back by the counter, so it has to be stable and it has to be visible. | تسلسل «ت» | models/legal_case_subject.py |
| A passport is per person, a commercial registration is per company. The checklist expands a per-subject requirement into one line for every name on the file's numbered list of persons. | قائمة «ت» | models/legal_doc_requirement.py |
| A tender does not merely demand a Chamber identity, it demands the Excellent grade. A grade requirement is satisfied by any grade at least as senior. | صنف ممتاز | models/legal_doc_requirement.py |
| Stamp Duty | طابع | models/legal_fee.py |
| The receipt number. Quoted back at every subsequent counter, so it is a column of its own and part of the file's search index. | رقم الوصل | models/legal_fee.py |
| What the counter calls it: registration fee, stamp duty, publication charges. | رسم التسجيل، طابع، أجور نشر | models/legal_fee_rule.py |
| Stamp Duty | طابع | models/legal_fee_rule.py |
| What the department calls it, e.g. “General power of attorney for Mr Ahmed at the Tax Commission”. | وكالة عامة للسيد أحمد لدى الضرائب | models/legal_poa.py |
| The number the notary put on it. Quoted at the counter, so it is searchable rather than buried in a scan. | الكاتب العدل | models/legal_poa.py |
| Agent | الوكيل | models/legal_poa.py |
| An advocate's power of attorney is registered with the Bar Association and some counters - the courts above all - will accept nothing else. | وكالة | models/legal_poa.py |
| Which branch of the Bar Association registered it. | نقابة المحامين | models/legal_poa.py |
| General | عامة | models/legal_poa.py |
| Specific | خاصة | models/legal_poa.py |
| Litigation | بالمرافعة | models/legal_poa.py |
| A specific power of attorney names the transaction it covers, and a counter reads it narrowly. Recording the scope is what lets the gate refuse a general errand presented on a litigation deed. | وكالة | models/legal_poa.py |
| Notary | الكاتب العدل | models/legal_poa.py |
| Revoked | معزولة | models/legal_poa.py |
| A revoked power of attorney needs a reason. The agent will ask, the counter will ask, and in six months so will the auditor. | وكالة | models/legal_poa.py |
| The power of attorney “%s” has been revoked. | الوكالة | models/legal_poa.py |
| The power of attorney “%s” has not been registered yet. | الوكالة | models/legal_poa.py |
| The power of attorney “%(name)s” lapsed on %(date)s. | الوكالة | models/legal_poa.py |
| The power of attorney “%(name)s” is not registered at %(body)s, and the counter will not accept it. | الوكالة | models/legal_poa.py |
| A power of attorney that was in force cannot be deleted - files were presented under it. Revoke it with a reason, or archive it. | وكالة | models/legal_poa.py |
| A step that cannot be taken without a signed and stamped official letter. | كتاب رسمي | models/legal_procedure_step.py |
| The sentence pre-filled into the contact note when a call is logged from this step, e.g. 'We followed up with the section and they advised the file is under review'. | راجعنا الشعبة وأفادوا بأن المعاملة قيد التدقيق | models/legal_procedure_step.py |
| The endorsement itself, in the words the counter uses: the tax-liens stamp, the no-objection confirmation. | ختم الحجوزات الضريبية، تأييد عدم الممانعة | models/legal_procedure_step.py |
| The button the clerk presses, in their words: “Transfer the file to the Residency Directorate”, “Return for correction”, “Conditional approval”. | «تحويل المعاملة إلى دائرة الإقامة»، «إعادة للتصحيح»، «قبول مشروط» | models/legal_procedure_transition.py |
| Blocks the move outright when no power of attorney on the file is in force for this body. The counter will refuse it, so pretending otherwise only moves the failure to the pavement outside the ministry. | وكالة | models/legal_procedure_transition.py |
| One entry-visa letter routinely covers eight experts on a numbered list, so the people are rows on the file rather than one field - and a procedure that is about the company has no such list at all. | قائمة «ت» | models/legal_procedure_type.py |
| Required where the counter will not deal with anyone who is not on the power of attorney - which is most counters, most of the time. | الوكالة | models/legal_procedure_type.py |
| Application for a limited company incorporation licence | طلب إجازة تأسيس شركة محدودة | views/legal_case_views.xml |
| Who carries the file today | من يحمل المعاملة اليوم | views/legal_case_views.xml |
| The numbered table of persons the letter prints. The Arabic name is what the ministry files and the Latin name is what the passport says - both are printed on the same page, so both are stored. | جدول «ت» | views/legal_case_views.xml |
| A file walks a procedure whose steps are configuration, not code. Configure the procedure once and every file after it knows which counter is next, what the counter will demand and when to start chasing. | المعاملة | views/legal_case_views.xml |
| Stamped certified true copy, two copies, in the applicant's own folder. | طبق الأصل | views/legal_doc_requirement_views.xml |
| Annual tax declaration | الإقرار الضريبي السنوي | views/legal_obligation_views.xml |
| General power of attorney at the General Commission for Taxes | وكالة عامة لدى الهيئة العامة للضرائب | views/legal_poa_views.xml |
| Record the power of attorney before somebody needs it | الوكالة | views/legal_poa_views.xml |
| Submit the application to the registration section | تقديم الطلب إلى شعبة التسجيل | views/legal_procedure_step_views.xml |
| Awaiting registration | بانتظار التسجيل | views/legal_procedure_step_views.xml |
| Files submitted but not yet registered | الملفات المقدمة والتي لم تُسجل بعد | views/legal_procedure_step_views.xml |
| No files are awaiting registration - everything submitted has been registered | لا توجد معاملات بانتظار التسجيل - كل ما قُدم قد سُجل | views/legal_procedure_step_views.xml |
| We followed up with the section and they advised the file is under review | راجعنا الشعبة وأفادوا بأن المعاملة قيد التدقيق | views/legal_procedure_step_views.xml |
| A clearance certificate is twenty-two windows inside one step. Listing them here is what turns “the file is at the Tax Commission” into “it is at window 7 waiting for the tax-liens stamp”. | براءة ذمة؛ ختم الحجوزات الضريبية | views/legal_procedure_step_views.xml |
| Transfer the file to the Residency Directorate | تحويل المعاملة إلى دائرة الإقامة | views/legal_procedure_transition_views.xml |
| Limited company incorporation | تأسيس شركة محدودة | views/legal_procedure_type_views.xml |
| The name of a transition is the button the clerk presses, so write it in their words - “Transfer the file to the Residency Directorate”, not “Approve”. | تحويل المعاملة إلى دائرة الإقامة | views/legal_procedure_type_views.xml |
| Missing documents: they want a recent clearance certificate and a certified copy of the lease contract | نقص في المستمسكات: يطلبون تأييد براءة ذمة حديث وصورة مصدقة من عقد الإيجار | wizard/legal_case_return_views.xml |
