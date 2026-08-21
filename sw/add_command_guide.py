# دليل إضافة أوامر جديدة للبوت
# ===========================================
# 
# الخطوة 1: التقاط الأمر
# -----------------------
# شغّل:
#   frida -D emulator-5554 -n Empire -l capture_cmds.js -q
# ثم نفّذ الإجراء في اللعبة وستظهر:
#
#   >>> SEND cmd=XXXX | {"cmd":"XXXX", "data":{...}}
#   <<< RECV cmd=XXXX | {"cmd":"XXXX", "result":{...}}
#
# ===========================================
# 
# الخطوة 2: فهم البنية
# ---------------------
# كل أمر له:
#   cmd    - رقم الأمر (مثل "1033" للميناء)
#   subcmd - عادةً "2" عند الإرسال، "1" للـ heartbeat
#   data   - البيانات المرسلة (dict) 
#   result - البيانات المستقبلة (في الـ response)
#
# ===========================================
#
# الخطوة 3: إضافة الأمر في onemt_bot.py
# ----------------------------------------
# انسخ هذا الـ template وعدّله:

# --- TEMPLATE ---

class GateBotExample:
    """مثال توضيحي - الكود الحقيقي في GateBot بـ onemt_bot.py"""
    
    # =============================================
    # مثال 1: أمر بسيط بدون بيانات
    # ← من الالتقاط: >>> SEND cmd=1033 | {}
    # =============================================
    def port_mission(self):
        """مهمة الميناء - بسيطة بدون data"""
        self.send_cmd("1033", "2", {})
    
    # =============================================
    # مثال 2: أمر مع بيانات
    # ← من الالتقاط: >>> SEND cmd=XXXX | {"x":150,"y":200,"type":1}
    # =============================================
    def attack_city(self, x: int, y: int, troop_count: int):
        """هجوم على قلعة في الإحداثيات المحددة"""
        self.send_cmd("XXXX", "2", {
            "x": x,
            "y": y,
            "type": 1,
            "count": troop_count,
        })
    
    # =============================================
    # مثال 3: أمر يحتاج انتظار Response
    # ← من الالتقاط: SEND cmd=YYYY | {"uid":12345}
    #                RECV cmd=YYYY | {"castle":{"level":15,"troops":5000}}
    # =============================================
    def get_castle_info(self, player_uid: int):
        """استعلام عن معلومات قلعة لاعب"""
        self.send_cmd("YYYY", "2", {"uid": player_uid})
        # الـ response سيصل في recv_loop تحت نفس الـ cmd
    
    # =============================================
    # كيف تعالج الـ response في recv_loop
    # =============================================
    def recv_loop(self):
        while self.alive:
            # ... استقبال الـ packet ...
            
            c   = r.get('content', {})
            cmd = c.get('cmd', '?')
            
            # أضف هنا معالجة الـ cmds الجديدة:
            if cmd == "1033":
                # مهمة الميناء - عادةً لا تحتاج معالجة
                pass
            
            elif cmd == "XXXX":
                # الهجوم
                result = c.get('result', {})
                print(f"Attack result: {result}")
            
            elif cmd == "YYYY":
                # معلومات القلعة
                castle = c.get('castle', {})
                print(f"Castle level: {castle.get('level')}")
                print(f"Castle troops: {castle.get('troops')}")


# ===========================================
# ملاحظات مهمة:
# ===========================================
# 1. subcmd="2" للإرسال العادي، subcmd="1" للـ heartbeat
# 2. بعض الأوامر تحتاج البيانات كـ list وليس dict
# 3. الـ response قد يأتي مع تأخير - استخدم threading.Event للانتظار
# 4. بعض الأوامر تُرسل push notifications للـ clients الآخرين

if __name__ == "__main__":
    print("""
=== دليل استخدام capture_cmds.js ===

1. شغّل الـ capture:
   frida -D emulator-5554 -n Empire -l capture_cmds.js -q

2. نفّذ في اللعبة:
   - انقر على قلعة لاعب آخر
   - اضغط استطلاع
   - اضغط هجوم
   - افتح القائمة/المهام

3. ستظهر:
   >>> SEND cmd=XXXX | {"data":"..."}   ← ما يُرسله اللعبة
   <<< RECV cmd=XXXX | {"result":"..."}  ← ما يستقبله

4. في onemt_bot.py - GateBot class، أضف method جديدة:
   def my_new_action(self, param1, param2):
       self.send_cmd("XXXX", "2", {"param1": param1, "param2": param2})

5. لمعالجة الـ response، أضف في recv_loop:
   elif cmd == "XXXX":
       result = c.get('result', {})
       # افعل شيئاً بالـ result
""")
