# Iraqi Corporate Legal-Department Operating Model — Domain Research (research_iraqi)

Audit input for the legal suite redesign (BEFORE state). Researched 2026-08-31 against Iraqi
government, judicial and legislative sources. All Arabic terms below are the professional register
actually used by Iraqi legal directorates (دوائر/أقسام قانونية), not generic MSA.

## Summary

Iraqi corporate legal departments — in state companies (Fao Engineering, Oil Exploration Co.),
ministries (Planning) and mixed/private companies under Companies Law 21/1997 — run a remarkably
uniform operating model built around seven recurring functions: (1) legal opinions/consultations
(الرأي القانوني) answering other departments, (2) contract drafting, vetting and obligation
follow-up under the Government Contracts Instructions 2/2014 regime (bonds, delay penalties,
takeover certificates), (3) litigation and representation before a fixed court hierarchy (بداءة →
استئناف → تمييز, plus specialised عمل/جنح/جنايات/تحقيق and the administrative judiciary of مجلس
الدولة), with short, unforgiving statutory appeal windows (10/15/30/7 days from التبليغ),
(4) powers of attorney and notarisation through كاتب العدل under Law 33/1998 (general vs special
POA, formal revocation by إنذار وعزل), (5) corporate-registry compliance with دائرة تسجيل الشركات
(founding contract, GA minutes ratification, annual accounts, amendment notices, daily fines),
(6) administrative investigation committees under the State Employees Discipline Law 14/1991, and
(7) the official correspondence register (الصادر/الوارد, كتاب رسمي with العدد والتاريخ, secrecy
grades, archival إضبارة filing). The current codebase already models a gov-body registry, a
procedure-driven case engine with SLA, a POA object and a locked numbered correspondence register —
but it is oriented to *administrative transactions* (معاملات) with government windows, and has **no
court hierarchy, no hearing (جلسة) object, no statutory appeal-period engine, no legal-opinion
workflow and no contract lifecycle**, which are the core of a corporate legal department per the
sources below.

## Findings

| Area | Current | Problem | Severity | Target |
|---|---|---|---|---|
| domain | Deadlines are generic SLA rules (`legal_sla_rule.py`) and one free `date_deadline` on the case (`legal_case.py:313`) | No statutory appeal-period engine. Iraqi appeal windows are short and fatal: اعتراض على الحكم الغيابي 10 days, استئناف 15 days, تمييز 30 days (7 days for قرارات), labor-court challenge 30 days — all counted from تاريخ التبليغ. Missing one loses the case irrecoverably | critical | Deadline engine keyed to (court degree, remedy type) that auto-computes the window from the recorded tabligh date, flags non-extendable periods, and feeds the unified deadline board |
| domain | `legal.gov.body` is a generic registry (`legal_gov_body.py:61`) with a free-text type; grep finds no `court`/`hearing` model in legal_core or legal_procedure | No real courts registry. The Iraqi hierarchy is fixed and knowable (التمييز الاتحادية؛ استئناف ×16 بصفتيها؛ بداءة، أحوال شخصية، عمل، تحقيق، جنح، جنايات، أحداث؛ قضاء إداري/قضاء موظفين/إدارية عليا) and drives venue, appeal routing and deadlines | high | First-class court registry (or typed gov-body subtype) with degree, competence, seat/محافظة and parent appeal court, pre-seeded from the SJC structure |
| domain | Cases have `round` (`legal_case.py:131`) and step phases, but no session object | No hearing (جلسة/مرافعة) model: date, courtroom, attendance, postponement reason (قرار التأجيل), what was decided, and next hearing date — the daily bread of a litigation desk | high | `legal.hearing` linked to case + court, auto-creating the next-hearing deadline and a hearing-log printout for the manager's morning review |
| domain | No consultation/opinion model anywhere in the suite | Legal opinions (الرأي القانوني/الاستشارة القانونية) are the #1 recurring internal service per MoP formations decree and the Fao bylaw, with a request→study→opinion→approval flow and citable legal basis | high | `legal.opinion` intake from requesting department, question, reasoned opinion with legal-basis citations, approval chain, searchable precedent library |
| domain | `legal.obligation.schedule` (`legal_obligation.py:17`) is a compliance calendar (frequency, due month/day, penalty note); no contract object | No contracts lifecycle. Iraqi practice (تعليمات تنفيذ العقود الحكومية 2/2014) revolves around التأمينات الأولية وخطاب ضمان حسن التنفيذ (5%)، الغرامات التأخيرية بسقف تعاقدي، تمديد المدة، الاستلام الأولي والنهائي، فترة الصيانة، سحب العمل | high | Contract model with parties, value (IQD), bond records with expiry alerts, delay-penalty accrual against ceiling, receptions and obligations generated onto the unified deadline board |
| domain | POA exists (`legal_poa.py`) with scope selection, revocation fields, lawyer/bar fields — good bones | `notary_office` is a free Char (`legal_poa.py:104`); no عامة/خاصة typing tied to what the agent may legally do, no formal إنذار وعزل الوكيل revocation document trail, no expiry alerting | medium | Type the POA (عامة/خاصة/دوائر الدولة), link the issuing كاتب العدل office to the body registry, model revocation as the notarised عزل procedure with its ورقة تبليغ, and surface expiring/limited POAs |
| domain | Fao bylaw Art. 7: court representation happens "بتفويض من المدير العام"; case has `user_id`/`runner_partner_id` only | No record of the authorization (التخويل/التفويض) under which an employee or hired محامي represents the company in a given case — an auditor's first question | medium | Per-case representation block: authorizing instrument, representative, POA reference, hired-counsel engagement |
| domain | No investigation-committee model | Administrative investigative committees (اللجان التحقيقية) under Law 14/1991 are a statutory legal-department duty: a lawyer member is mandatory, minutes + reasoned recommendations go to the department head | medium | Committee file: formation order, members, sessions, محضر, recommendation, resulting penalty — feeding the deadline board |
| domain | `legal_iq_registrar` module exists as a content pack | Registrar obligations of Companies Law 21/1997 not encoded as dated events: amendment notices, GA minutes ratification, annual accounts to دائرة تسجيل الشركات, daily late fines (secondary source: up to 300,000 IQD/day — verify against official text) | medium | Seed obligation schedules for each statutory registrar event with legal-basis citation and verified periods |
| domain | Correspondence register is strong: locked number/date/book (`legal_correspondence.py:77`), direction, secrecy عادي/سري (`:111`), retention years | Secrecy grades incomplete vs practice (سري وشخصي, and urgency عاجل/مستعجل handling); no archival إضبارة (file/folder) reference for the 200-document filing convention | low | Add سري وشخصي grade + urgency flag + archival file reference to the entry |
| domain | Arabic exists in defaults (e.g. salutation "السيد المدير العام المحترم", `legal_gov_body.py:127`) but labels are English-first | Terminology must match the Iraqi register (شعبة الدعاوى/الحقوق، شعبة العقود، شعبة الاستشارات، الرأي القانوني، كتاب رسمي…) — the glossary below — for the department to trust the system | medium | Adopt the §9 glossary as the canonical ar_001 translation layer; Arabic-first RTL labels throughout |
| domain | No real-estate transaction tracking | Fao bylaw explicitly assigns شراء/بيع/إيجار/استئجار الأراضي والعقارات and estate administration to the legal section — common in state companies | low | Optional property-transaction case type using the existing procedure engine |

## 1. Source log — reachable vs not

**Reachable (fetched full page content in this session):**

| Source | URL | Yield |
|---|---|---|
| مجلس القضاء الأعلى — النظام القضائي في العراق | https://www.sjc.iq/Judicial-system.php | Full court hierarchy and competences (§3) |
| وزارة العدل — دائرة الكتاب العدول | https://moj.gov.iq/tashkelat.10/ | Notary functions, POA/bail/undertaking notarisation, bail cancellation rules (§5) |
| النظام الداخلي لشركة الفاو العامة للمقاولات الهندسية (dorar wiki law/1185) | http://wiki.dorar-aliraq.net/iraqilaws/law/1185.html | Art. 7: full duty list of the legal section + its two shu'ab (العقود؛ الدعاوى والحقوق) (§2) |
| تنظيم تشكيلات واختصاصات وزارة التخطيط (dorar wiki law/7439) | http://wiki.dorar-aliraq.net/iraqilaws/law/7439.html | Legal directorate's four sections: الاستشارات والعقود، الحقوق، المقاولين، الأرشيف والمراسلات (§2) |
| قانون الشركات 21/1997 شرح — iraqilaws.com | https://www.iraqilaws.com/2023/10/21-1997.html | Company types, founding, periodic registrar obligations, fines (§6 — periods flagged for verification) |
| دائرة تسجيل الشركات — وزارة التجارة | https://tasjeel.mot.gov.iq/test2/ | Service/procedure catalogue of the registrar (§6) |
| شركة الاستكشافات النفطية OEC | https://www.oec.oil.gov.iq/... | Confirms القسم القانوني in the org structure; **no duty detail published** |

**Reachable via search snippets only (not fetched):**
مدد الطعن في قانون المرافعات المدنية 83/1969 (dorar forum + alabbadilawfirm.com);
قانون العمل 37/2015 labor-court 30-day challenge (iraqilaws.com, uomus.edu.iq lecture PDF);
تعليمات تنفيذ العقود الحكومية 2/2014 (scribd, uomosul.edu.iq PDF, mop.gov.iq);
قانون كتاب العدول 33/1998 (cm.qu.edu.iq, dorar wiki law/17106);
عزل الوكيل procedure (mofa.gov.iq consular pages Los Angeles/Cairo);
قانون انضباط موظفي الدولة 14/1991 investigative committees (tu.edu.iq PDF, dorar wiki law/13754);
administrative judiciary competences (iraqfsc.iq, almerja.com);
Iraqi official correspondence/filing practice (uokerbala.edu.iq, scribd, iraqnla.gov.iq).

**Not reachable / no usable content:**

- https://icdi.iq/companys_departments/details/1 (Iraqi Co. for Developing Investment legal dept page) — **HTTP 404**; only the search snippet survived ("يتولى القسم تمثيل الشركة قانونياً أمام القضاء العراقي… كما أنه يقدم الاستشارات القانونية").
- faoco.moch.gov.iq (Fao Engineering official site) — not fetched directly; the company's bylaw text on dorar wiki was used instead (better: it is the legal instrument itself).
- mop.gov.iq legal directorate page — site reachable but no dedicated duties page found; the formations decree on dorar wiki used instead.
- Iraq Oil Exploration Company legal-department duty statement — the OEC site names the القسم القانوني but publishes no duty breakdown anywhere found.

## 2. The corporate legal-department operating model

Distilled from the Fao bylaw Art. 7 (النظام الداخلي, dorar law/1185), the Ministry of Planning
formations decree (dorar law/7439), the ICDI snippet and the OEC structure. The functions recur
across every source:

1. **الاستشارات والرأي القانوني** — study and vet the legal aspects of every company activity;
   answer written consultation requests from other departments with a reasoned opinion citing its
   legal basis. MoP has a dedicated قسم الاستشارات والعقود.
2. **العقود** — draft, standardise and vet contracts; follow up execution of their clauses
   (متابعة تنفيذ بنودها); certify الكفالات والتعهدات per applicable resolutions; participate in
   international negotiations (MoP). Fao dedicates a شعبة العقود.
3. **الدعاوى والتمثيل القضائي** — represent the company before courts and other bodies **by
   delegation from the director general** (بتفويض من المدير العام); sign تبليغات; engage and
   instruct outside محامون; pursue appeals. Fao's second شعبة: الدعاوى والحقوق; MoP's قسم الحقوق.
4. **الوكالات والتوثيق** — prepare and register POAs at كاتب العدل; manage revocations (§5).
5. **التحقيقات الإدارية** — sit on/chair investigative committees under Law 14/1991; a
   law-graduate member is mandatory; produce محضر with reasoned recommendations.
6. **العقارات والأملاك** — all buy/sell/lease transactions of land and property for company
   purposes and administration of company estates (Fao Art. 7).
7. **الالتزامات النظامية** — keep the company compliant with دائرة تسجيل الشركات, tax (براءة
   الذمة), and social security; ratify GA/board minutes; file accounts (§6).
8. **اللوائح والأنظمة** — draft and periodically restudy internal regulations and instructions.
9. **عضوية اللجان** — membership of committees requiring legal cadres (tenders, sales, leases).
10. **المراسلات والأرشيف** — the legal registry of official letters; MoP has a dedicated قسم
    الأرشيف والمراسلات (§8).

Typical structure vocabulary: الدائرة القانونية (ministry level) → القسم القانوني (company level)
→ شُعَب: شعبة العقود، شعبة الدعاوى (الحقوق)، شعبة الاستشارات (الرأي)، شعبة التحقيقات، شعبة
التوثيق/الأرشيف. Managed by مدير حاصل على شهادة جامعية أولية في القانون.

## 3. Courts registry — the canonical hierarchy (per مجلس القضاء الأعلى)

Ordinary judiciary (sjc.iq):

| المحكمة | الاختصاص | ملاحظات |
|---|---|---|
| محكمة التمييز الاتحادية | الرقابة القضائية على جميع المحاكم؛ تدقيق الأحكام | رئيس + 5 نواب + ≥30 قاضياً |
| محكمة استئناف المنطقة | الهيئة القضائية العليا في المحافظة؛ تنظر الطعون بصفتها الأصلية وبصفتها التمييزية | 16 محكمة — واحدة لكل محافظة وبغداد اثنتان (الكرخ/الرصافة) |
| محكمة البداءة | الدعاوى المدنية: البيع، الإيجار، الالتزامات، الديون | قاضٍ واحد؛ في كل مركز محافظة أو قضاء |
| محكمة الأحوال الشخصية | الزواج، الطلاق، النفقة، شؤون العائلة | |
| محكمة العمل | نزاعات العمل والعمال (قانون العمل 37/2015) | طريق الطعن بقرارات لجنة إنهاء الخدمة |
| محكمة التحقيق | التحقيق في الجرائم كافة وتحديد درجتها قبل الإحالة | |
| محكمة الجنح | الجرائم المعاقب عليها بخمس سنوات فأقل | |
| محكمة الجنايات | الجرائم التي تتجاوز عقوبتها خمس سنوات | |
| محكمة الأحداث | من هم دون 18 سنة | |

Administrative judiciary (قانون مجلس الدولة — iraqfsc.iq/almerja):

| المحكمة | الاختصاص |
|---|---|
| محكمة القضاء الإداري | صحة الأوامر والقرارات الإدارية الصادرة عن الموظفين والهيئات في دوائر الدولة والقطاع العام؛ منازعات العقود الإدارية؛ التعويض عن القرارات غير المشروعة |
| محكمة قضاء الموظفين | الحقوق الوظيفية: الرواتب، الترقيات، النقل، العقوبات الانضباطية |
| المحكمة الإدارية العليا | الطعون بقرارات المحكمتين أعلاه؛ قراراتها باتة |

For a corporate legal system the registry must carry: court name, degree (أول/ثانٍ/تمييز), type,
seat (المحافظة/القضاء), and parent appeal court — because the appeal route and its window are a
function of these attributes, not free text.

## 4. Statutory deadline practice (مدد الطعن)

All windows run from the day after التبليغ (service) or its legal equivalent. Verified via
مرافعات مدنية 83/1969 secondary sources and labor-law sources this session:

| الإجراء | المدة | الأساس |
|---|---|---|
| الاعتراض على الحكم الغيابي | 10 أيام | مرافعات 83/1969 |
| الاستئناف | 15 يوماً | مرافعات 83/1969 |
| التمييز — الأحكام | 30 يوماً | مرافعات 83/1969 |
| التمييز — القرارات القابلة للطعن | 7 أيام | مرافعات 83/1969 |
| الطعن بقرار لجنة إنهاء الخدمة أمام محكمة العمل | 30 يوماً | قانون العمل 37/2015 (عبء إثبات صحة الإنهاء على صاحب العمل) |
| التظلم من القرار الإداري ثم الطعن أمام القضاء الإداري | 30 يوماً تظلم / 60 يوماً طعن — **verify against قانون مجلس الدولة 65/1979 المعدل** | not fetched this session |
| إشعار المسجل بتعديل عقد الشركة | 7 أيام (secondary source — verify) | شركات 21/1997 |
| الحسابات الختامية السنوية للمسجل | 60 يوماً من نهاية السنة المالية per iraqilaws.com summary — **official text commonly cited as within 6 months؛ verify before encoding** | شركات 21/1997 |

Design consequence: these are *statutory*, non-negotiable, court-degree-dependent periods —
qualitatively different from internal SLAs. A professional system computes them from the recorded
tabligh date, marks them non-extendable, and escalates before expiry.

## 5. كاتب العدل and POA practice (قانون الكتاب العدول 33/1998)

- The notary (الكاتب العدل, دائرة الكتاب العدول/وزارة العدل) authenticates **all legal
  dispositions unless excepted by special text**: الوكالات بكافة أنواعها, الكفالات (والغاؤها بطلب
  الجهة المستفيدة أو بحكم قضائي), العقود والتعهدات, الإقرارات, الترجمات بحضور مترجم محلّف,
  documents destined for use abroad.
- **الوكالة العامة** empowers the agent over the principal's affairs generally; **الوكالة الخاصة**
  is limited to named acts. Civil Code 40/1951 Art. 927: "الوكالة عقد يقيم به شخص غيره مقام نفسه
  في تصرف جائز معلوم". Court representation by a محامٍ requires the advocate's bar registration.
- **Revocation** is itself a formal notarised act — استمارة إنذار وعزل الوكيل with ورقة تبليغ; the
  agent becomes أجنبياً عن الموكل only after proper عزل. A general POA "لا ينتهي مفعولها إلا
  بإلغائها". Corporate practice therefore tracks: issuing notary office and number, type, scope,
  agents, and the revocation instrument.
- Consulates perform the same function abroad (mofa.gov.iq consular pages).

## 6. Companies Law 21/1997 (as amended 2004) and دائرة تسجيل الشركات

Company forms: مساهمة (خاصة/مختلطة)، محدودة المسؤولية، تضامنية، مشروع فردي، شركة بسيطة. Founding:
notarised عقد تأسيس filed with مسجل الشركات; **شهادة التأسيس** confers الشخصية المعنوية. The
registrar's actual service catalogue (tasjeel.mot.gov.iq): founding of national companies, فروع
الشركات الأجنبية, الوكالات التجارية licensing, تعديل عقود التأسيس, زيادة رؤوس الأموال, التحويل
والاندماج والتصفية, تصديق محاضر مجالس الإدارة والهيئات العامة, share transfers/inheritance/seizure,
تدقيق الحسابات الختامية, الحجوزات والموانع, answering government inquiries.

Periodic obligations of an established company (the legal department's compliance calendar):
annual final accounts, GA minutes filing/ratification, amendment notices within statutory days,
managing المدير المفوض records — with daily late fines (secondary: up to 300,000 IQD/day) and
criminal exposure for false statements. Related recurring files: براءة الذمة الضريبية (tax
clearance), الضمان الاجتماعي clearances, chamber-of-commerce membership renewals — matching the
existing `legal_iq_tax` / `legal_iq_social_security` / `legal_iq_chamber` content packs.

## 7. Government contracts practice (تعليمات تنفيذ العقود الحكومية 2/2014)

The regime every state-company legal section administers (uomosul PDF, mop.gov.iq): contract types
مقاولة/تجهيز/استشارية; **التأمينات الأولية** (bid bond) and **خطاب ضمان حسن التنفيذ** (~5% of
contract value, released after final reception); **الغرامات التأخيرية** accrued per day against a
contractual ceiling; extensions (المدد الإضافية) by justified order; أوامر الغيار (variation
orders); **الاستلام الأولي** then **الاستلام النهائي** after فترة الصيانة/الإدامة; and سحب العمل
(withdrawal of works) with its legal consequences on default. The legal section certifies the
bonds and pursues الإخلال بالالتزامات التعاقدية. These are precisely the "obligations" the target
spec's contracts+obligations lifecycle must represent — bond expiry dates and penalty ceilings are
deadline-board material.

## 8. Official correspondence practice

Iraqi departmental practice (uokerbala.edu.iq, iraqnla.gov.iq, filing instructions): every كتاب
رسمي carries **العدد والتاريخ** (sequential number + date) from a specific book; separate
**سجل الصادر** and **سجل الوارد**, each in ordinary and secret series (عادي/سري, plus سري وشخصي
addressed personally); urgency markings (عاجل); filing by الإضبارة with a general-number
convention (~200 documents per file); the margin annotation (الهامش/التأشيرة) routes the letter
internally. The current `legal_correspondence` module already implements the two-number reality
(our_number/their_number), book-locked numbering and register-level secrecy/retention — closest of
all modules to real practice.

## 9. Terminology glossary (professional Iraqi Arabic — UI canon)

| المصطلح | English (UI) | Notes |
|---|---|---|
| الدائرة القانونية / القسم القانوني | Legal Department | دائرة at ministry level, قسم at company level |
| شعبة الدعاوى / شعبة الحقوق | Litigation Section | Fao: "الدعاوى والحقوق"؛ MoP: "قسم الحقوق" |
| شعبة العقود | Contracts Section | |
| شعبة الاستشارات / الرأي القانوني | Legal Opinion Section | deliverable: الرأي القانوني |
| الاستشارة القانونية / المشورة | Legal consultation | request from a department |
| الدعوى / عريضة الدعوى / اللائحة الجوابية | Case / statement of claim / reply | المدعي، المدعى عليه، الشخص الثالث |
| الجلسة / المرافعة / التأجيل | Hearing / pleading / postponement | قرار التأجيل + سببه |
| التبليغ / ورقة التبليغ | Service of process | starting point of every طعن window |
| الإنذار (العدلي) | (Notarised) formal notice | served via كاتب العدل |
| طرق الطعن: اعتراض على الحكم الغيابي، استئناف، تمييز، تصحيح القرار التمييزي، إعادة المحاكمة، اعتراض الغير | Remedies | each with its own window |
| الحجز الاحتياطي | Precautionary attachment | |
| الوكالة العامة / الخاصة، الموكل، الوكيل، عزل الوكيل | General/special POA, principal, agent, revocation | via كاتب العدل |
| الكفالة / التعهد / الإقرار | Bail-guarantee / undertaking / declaration | notarised |
| خطاب ضمان حسن التنفيذ / التأمينات الأولية | Performance bond / bid bond | ~5% practice |
| الغرامات التأخيرية | Delay penalties | daily, capped |
| الاستلام الأولي / النهائي، فترة الصيانة | Preliminary/final reception, maintenance period | |
| سحب العمل | Withdrawal of works | contractor default |
| عقد التأسيس / شهادة التأسيس / المدير المفوض | Founding contract / certificate of incorporation / managing director | شركات 21/1997 |
| الهيئة العامة / محضر الاجتماع / الحسابات الختامية | General assembly / minutes / final accounts | ratified at the registrar |
| براءة الذمة | Clearance certificate | tax/social security |
| اللجنة التحقيقية / المحضر / التوصيات | Investigative committee / minutes / recommendations | قانون 14/1991 |
| الكتاب الرسمي، العدد والتاريخ، الصادر/الوارد، سري، سري وشخصي، عاجل، الإضبارة، الهامش | Official letter, ref+date, outgoing/incoming, secret, secret-personal, urgent, file, margin note | |
| الرسوم العدلية / رسم الدعوى | Court fees | verify current tariff before encoding |

## 10. Document type catalogue

كتاب رسمي (صادر/وارد) • مذكرة داخلية • رأي قانوني • استشارة (طلب رأي) • عقد + ملاحق (ملحق
عقد/أمر غيار) • خطاب ضمان (أولي/حسن تنفيذ) • كفالة • تعهد • إقرار • وكالة عامة/خاصة • إنذار
وعزل وكيل • إنذار عدلي • عريضة دعوى • لائحة جوابية • محضر جلسة • قرار حكم • لائحة استئنافية /
لائحة تمييزية • محضر لجنة تحقيقية • أمر إداري (تشكيل لجنة، تخويل) • محضر هيئة عامة/مجلس إدارة •
عقد تأسيس • شهادة تأسيس • إجازة/ترخيص/هوية غرفة تجارة • براءة ذمة • ترجمة مصدقة.

## 11. Mapping to the current codebase (BEFORE state)

- `custom_addons/legal_core/models/legal_gov_body.py:61` — `legal.gov.body` with `body_type_id`
  (`:98`), hierarchy, letterhead fields, Arabic salutation default (`:127`). Right substrate for a
  courts registry, but no court degree/appeal-parent semantics; **no court-typed data found**.
- `custom_addons/legal_core/models/legal_jurisdiction.py:5` — jurisdiction tree exists; could carry
  the محافظة seat axis of courts.
- `custom_addons/legal_procedure/models/legal_case.py` — procedure-engine case: `kind` is a desk
  orientation ("Sitting With", `:113`), `round` (`:131`), `body_id` (`:146`), one `date_deadline`
  (`:313`), SLA fields (`:342-:356`). Grep over `legal_core/models` and `legal_procedure/models`
  finds **no `hearing` and no `court` class or field** — litigation is not modelled.
- `custom_addons/legal_procedure/models/legal_sla_rule.py` — internal SLA only; no statutory-period
  computation from a tabligh date (§4).
- `custom_addons/legal_procedure/models/legal_poa.py` — POA with `scope` (`:81`), free-text
  `notary_office` (`:104`), `revoked_on`/`revocation_reason` (`:123-124`), lawyer + bar fields
  (`:69-:80`). Missing: عامة/خاصة typing, notary-office registry link, عزل instrument, expiry (§5).
- `custom_addons/legal_procedure/models/legal_obligation.py:17` — `legal.obligation.schedule` with
  frequency/due date/`penalty_note`/`legal_basis`/`last_verified_on`: exactly the right shape for
  §6 registrar and §4 statutory events, but shipped content packs must be seeded and verified.
- `custom_addons/legal_correspondence/models/legal_register.py:5` + `legal_correspondence.py` —
  faithful صادر/وارد implementation: locked number/date/book/direction (`:77`), two-number model,
  secrecy عادي/سري (`:111`), retention. Gaps: سري وشخصي, urgency, إضبارة reference (§8).
- No model for: legal opinions (§2.1), contracts/bonds/penalties (§7), hearings (§3),
  investigative committees (§2.5), representation authorizations (§2.3).
