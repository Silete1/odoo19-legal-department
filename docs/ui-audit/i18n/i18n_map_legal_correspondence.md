# i18n seed - legal_correspondence

Arabic wording stripped from the source, keyed by the new English msgid.
Use each Arabic cell as the msgstr seed for its msgid in i18n/ar.po.

| English msgid | Arabic (msgstr seed) | file |
|---|---|---|
| Outgoing | صادر | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Incoming | وارد | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Internal | داخلي | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Ordinary | عادي | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Confidential | سري | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Our Number | رقم الصادر | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Our Date | تاريخ الصادر | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Their Number | رقم كتابهم | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Their Date | تاريخ كتابهم | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Government Body | الجهة | custom_addons/legal_correspondence/models/legal_correspondence.py |
| The section or the subdivision: which counter inside the body actually holds it. | القسم أو الشعبة | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Subject | م/ الموضوع | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Letter Text | نص الكتاب | custom_addons/legal_correspondence/models/legal_correspondence.py |
| For Information | للتفضل بالاطلاع | custom_addons/legal_correspondence/models/legal_correspondence.py |
| For Action | للإجراء اللازم | custom_addons/legal_correspondence/models/legal_correspondence.py |
| For Signature | للتوقيع | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Referred | أحيلت | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Hand Carried | تسليم باليد | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Courier | بريد سريع | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Email | بريد إلكتروني | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Portal | بوابة إلكترونية | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Registered Post | بريد مسجل | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Carried By | المراجع / المعتمد | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Paper | ورقي | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Online | إلكتروني | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Both | كلاهما | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Awaiting | بانتظار الرد | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Answered | مجاب | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Late | متأخر | custom_addons/legal_correspondence/models/legal_correspondence.py |
| True for an entry that actually answers the one it hangs off. A receipt, a contact note and our own reminder are all excluded, because a receipt proves the letter was received and closes nothing - and a system that counts a receipt as an answer reports a two-day turnaround at a body that has not yet read the file. Stored so that the reply board can be searched with one subquery instead of five that need not agree on which answer they matched. | وصل | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Draft | مسودة | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Registered | مسجل | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Void | ملغى | custom_addons/legal_correspondence/models/legal_correspondence.py |
| Outgoing | صادر | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| Incoming | وارد | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| Internal | داخلي | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| Is A Receipt | وصل | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| Is A Reminder | تذكير | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| A telephone call or a personal visit. It never touched the book, so it takes no number - but it is evidence, it moves the reply clock, and it suppresses the next chase when the counter has promised a date. | مراجعة | custom_addons/legal_correspondence/models/legal_correspondence_kind.py |
| Outgoing | صادر | custom_addons/legal_correspondence/models/legal_register.py |
| Incoming | وارد | custom_addons/legal_correspondence/models/legal_register.py |
| Internal | داخلي | custom_addons/legal_correspondence/models/legal_register.py |
| Ordinary | عادي | custom_addons/legal_correspondence/models/legal_register.py |
| Confidential | سري | custom_addons/legal_correspondence/models/legal_register.py |
| A confidential book is kept physically apart and its entries are visible only to the legal manager and the officers of the body concerned. | سري | custom_addons/legal_correspondence/models/legal_register.py |
| How long the book must be kept. The Council of Ministers' document-retention instructions put outgoing and incoming registers at ten years; a department that archives them sooner has destroyed evidence it was obliged to hold. | صادر، وارد | custom_addons/legal_correspondence/models/legal_register.py |
| Subject | م/ الموضوع | custom_addons/legal_correspondence/models/legal_letter_template.py |
| Copies To | نسخة منه إلى | custom_addons/legal_correspondence/models/legal_letter_template.py |
| Contact Date | تاريخ الاتصال | custom_addons/legal_correspondence/wizard/legal_contact_note_wizard.py |
| Spoke To | مع من | custom_addons/legal_correspondence/wizard/legal_contact_note_wizard.py |
| What They Said | ماذا قالوا | custom_addons/legal_correspondence/wizard/legal_contact_note_wizard.py |
| Promised For | وعد بـ | custom_addons/legal_correspondence/wizard/legal_contact_note_wizard.py |
| Subject | م/ الموضوع | custom_addons/legal_correspondence/wizard/legal_contact_note_wizard.py |
| Their Number | رقم كتابهم | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Their Date | تاريخ كتابهم | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Received On | تاريخ التسجيل | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Subject | م/ الموضوع | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| For Information | للتفضل بالاطلاع | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| For Action | للإجراء اللازم | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| For Signature | للتوقيع | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Referred | أحيلت | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Ordinary | عادي | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Confidential | سري | custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py |
| Reason | سبب الإلغاء | custom_addons/legal_correspondence/wizard/legal_correspondence_void_wizard.py |
| Our Number | رقم الصادر | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Date | التاريخ | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Their Number | رقم كتابهم | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Register | تسجيل | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Print Letter | طباعة الكتاب | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Record Contact Note | تدوين اتصال | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Void | إلغاء | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Void | ملغى | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Confidential | سري | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Subject | م/ الموضوع | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Request for a tax clearance certificate | طلب براءة ذمة ضريبية | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Our Register | سجلنا | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Allocated at registration | يُمنح عند التسجيل | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Their Reference | كتابهم | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| e.g. K/M/1234 | ك/م/١٢٣٤ | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Their internal file number | رقم الإضبارة لديهم | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| The Body | الجهة | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Hand-off | الإحالة | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| The Letter | الكتاب | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| After greetings, ... | تحية طيبة وبعد، ... | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Subject Table | جدول الموضوع | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Contact Note | التدوين | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Abu Ahmed - deputy head of the section | أبو أحمد - معاون مدير القسم | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| He said the file is with the legal adviser, and promised to look at it after Eid. | قال إن الإضبارة لدى المستشار القانوني، ووعد بمراجعتها بعد العيد. | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| This entry takes <b>no register number</b> - nothing entered the book. A date in <b>Promised For</b> moves the reply clock onto it and suppresses the next chase, so we stop ringing a body that has already answered. | وعد بـ | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Reply Clock | المهلة | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Scans | المرفقات | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Filed Copy | النسخة المحفوظة | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Void | الإلغاء | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Outgoing | صادر | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Incoming | وارد | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Internal | داخلي | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Awaiting Reply | بانتظار الرد | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Reply Overdue | متأخر عن الرد | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Answered | مجاب | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Confidential | سري | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Outgoing | صادر | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Incoming | وارد | custom_addons/legal_correspondence/views/legal_correspondence_views.xml |
| Correspondence Register | سجل الصادر والوارد | custom_addons/legal_correspondence/views/legal_correspondence_menus.xml |
| Register Incoming Letter | تسجيل كتاب وارد | custom_addons/legal_correspondence/views/legal_correspondence_menus.xml |
| Outgoing | صادر | custom_addons/legal_correspondence/views/legal_correspondence_menus.xml |
| Incoming | وارد | custom_addons/legal_correspondence/views/legal_correspondence_menus.xml |
| Sent back for completion | إعادة للاستكمال | custom_addons/legal_correspondence/views/legal_correspondence_kind_views.xml |
| A receipt proves the letter was <b>received</b>. It closes nothing and answers nothing, and it must never stop the reply clock - otherwise the department reports a two-day turnaround at a body that has not yet opened the file. | وصل | custom_addons/legal_correspondence/views/legal_correspondence_kind_views.xml |
| Outgoing | صادر | custom_addons/legal_correspondence/views/legal_correspondence_kind_views.xml |
| Incoming | وارد | custom_addons/legal_correspondence/views/legal_correspondence_kind_views.xml |
| Tax clearance request to the General Commission for Taxes | طلب براءة ذمة من الهيئة العامة للضرائب | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| Request for a tax clearance certificate for {today} | طلب براءة ذمة ضريبية لسنة {today} | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| After greetings, ... | تحية طيبة وبعد، ... | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| Legal Section&#10;Archives | القسم القانوني&#10;الأرشيف | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {our_number} - Our Number | رقم الصادر | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {our_date} - Our Date | تاريخ الصادر | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {their_number} - Their Number | رقم كتابهم | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {their_date} - Their Date | تاريخ كتابهم | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {today} - Today's Date | تاريخ اليوم | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {body} - The Body | الجهة | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {body_section} - The Section | القسم | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {body_reference} - Their File Number | رقم إضبارتهم | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {salutation} - The Salutation | عبارة المخاطبة | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {entity} / {entity_en} - Company Name | اسم الشركة | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {signatory} / {signatory_title} - Signatory And Title | الموقّع وصفته | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| {subject} - Subject | الموضوع | custom_addons/legal_correspondence/views/legal_letter_template_views.xml |
| General Outgoing Register | سجل الصادر العام | custom_addons/legal_correspondence/views/legal_register_views.xml |
| e.g. ق | ق | custom_addons/legal_correspondence/views/legal_register_views.xml |
| Outgoing | صادر | custom_addons/legal_correspondence/views/legal_register_views.xml |
| Incoming | وارد | custom_addons/legal_correspondence/views/legal_register_views.xml |
| Most departments keep two - outgoing and incoming. A department answering to three ministries keeps a book per ministry, and one holding classified files keeps a confidential book with a different key holder. All three are rows here, never a hard-coded list. | صادر، وارد، سري | custom_addons/legal_correspondence/views/legal_register_views.xml |
| Register Incoming Letter | تسجيل كتاب وارد | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| The Letter | الكتاب | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| e.g. K/M/1234 | ك/م/١٢٣٤ | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Tax assessment for 2025 | تقدير ضريبي لسنة ٢٠٢٥ | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Our Entry | قيدنا | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Scans | المرفقات | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Remark on receipt | ملاحظة عند التسلّم | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Register And Allocate Number | تسجيل ومنح الرقم | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Cancel | إلغاء | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Register Incoming Letter | تسجيل كتاب وارد | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Void Entry | إلغاء قيد | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| The reason: a duplicate letter, refused at the window, or never sent. | سبب الإلغاء: كتاب مكرر، أو رُفض عند الشباك، أو لم يُرسل. | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| The number stays in the book and is never reused. A voided entry keeps its place exactly as a struck-through line keeps its place in the paper register - otherwise the book has a gap nobody can explain years later. | الرقم يبقى في الدفتر ولا يُعاد استعماله. القيد الملغى يحتفظ بموضعه تماماً كما يبقى السطر المشطوب في السجل الورقي، وإلا صار في الدفتر ثغرة لا يستطيع أحد تفسيرها بعد سنوات. | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Confirm Void | تأكيد الإلغاء | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Cancel | تراجع | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Record Contact Note | تدوين اتصال | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Abu Ahmed - deputy head of the section | أبو أحمد - معاون مدير القسم | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| He said the file is with the legal adviser, and promised to look at it after Eid. | قال إن الإضبارة لدى المستشار القانوني، ووعد بمراجعتها بعد العيد. | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| This note takes no register number - it never went through the book at all. But the promised date moves the reply deadline onto it and stops the next chase, so the system does not keep chasing a body that has already answered. | هذا التدوين لا يأخذ رقماً في السجل - لم يمر بالدفتر أصلاً. لكن التاريخ الموعود ينقل مهلة الرد إليه ويوقف الملاحقة التالية، فلا يلاحق النظام جهةً أجابت فعلاً. | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Save Note | حفظ التدوين | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Record Contact Note | تدوين اتصال | custom_addons/legal_correspondence/wizard/legal_correspondence_wizard_views.xml |
| Official Letter (Pre-printed Paper) | كتاب رسمي - ورق مطبوع | custom_addons/legal_correspondence/report/legal_correspondence_reports.xml |
| Official Letter (Emblem Drawn) | كتاب رسمي - مع الترويسة | custom_addons/legal_correspondence/report/legal_correspondence_reports.xml |
| Registrar | مسؤول السجل | custom_addons/legal_correspondence/security/legal_correspondence_security.xml |
| The outgoing/incoming register, the official letter and the reply clock | سجل الصادر والوارد | custom_addons/legal_correspondence/__manifest__.py |
