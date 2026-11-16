STRAVEX BOT MUSIC V4: بوت فري فاير + تيليجرام
حسابات الموسيقى منفصلة + حساب أساسي مخصص للرقص والفرق

الملفات:
  accent.txt  ← حسابات الموسيقى (كل سطر  uid:pass)  لأوامر /music و /online و /em
  acces.txt   ← الحساب الأساسي (uid= و password= و region=)  لأوامر /evo /evos /dance /team
  ملاحظة: لا تحط حساب acces.txt داخل accent.txt (لو حطيته يستثنيه تلقائياً من المخزن).

التشغيل:
  pip install -r requirements.txt
  export TELEGRAM_BOT_TOKEN="توكن البوت"
  python main.py

الانضمام السريع (حسابات الموسيقى):
  البوت يجهز مسبقاً حسابات مسجلة دخول ومتصلة (WARM_BOTS، افتراضي 2). أول ما أحد يكتب /music يدخل فريقه فوراً بدون انتظار تسجيل الدخول، وبعدها يجهز بديل بالخلفية. وكل مرة ياخذ حساب عشوائي غير مشغول.

الحساب الأساسي: يبقى أونلاين دايم ويعيد الاتصال لحاله. ينفذ مهمة وحدة بنفس الوقت (لو مشغول يقول جرب بعد شوي).

أوامر تيليجرام (للجميع):
  /music <كود_الفريق> [أغنية]   /online   /play <رابط أو اسم>   /resume   /stop
  /em <كود_الفريق> [uid ...]    كل الرقصات (حساب موسيقى)
  بالحساب الأساسي:
    /dance <كود_الفريق> <uid ...> <رقم>
    /evo <كود_الفريق> <uid ...> <رقم>
    /team3 /team5 /team6 <uid>   (أو /3 /5 /6)

أوامر الأدمن فقط:
  /co                            يعرض كل أوامر الأدمن
  /evos <كود_الفريق> <uid>       كل الرقصات على لاعب وتتكرر بدون توقف (/stop للإيقاف)
  /on /off /status /allow /disallow /kick /unban /groups /admins /addadmin /deladmin /accounts /reload /addacc

داخل اللعبة (شات الفريق، بوتات الموسيقى):
  !help !play !search !stop !resume !status !sound !dance !em !evo_list !5 !3 !6 !leave

الخروج التلقائي (بوتات الموسيقى): يطلع من الفريق إذا بقى وحده (بعد 45 ثانية)، أو إذا ما صار نشاط ولا أغنية 20 دقيقة (IDLE_LEAVE_MINUTES).

المتغيرات: كلها في ملف .env.example (انسخه باسم .env محلياً، أو ضيفها في Variables على Railway).
المطلوب فقط: TELEGRAM_BOT_TOKEN + (MAIN_UID / MAIN_PASSWORD أو acces.txt) + (ACCOUNTS أو accent.txt).

ملاحظة: هذي النسخة ما فيها أوامر السبام.

الشكل: رسائل تيليجرام بتصميم بطاقات (ملف ui.py). غيّر الاسم من BOT_NAME، وعدّل الشكل من الدوال في ui.py.
