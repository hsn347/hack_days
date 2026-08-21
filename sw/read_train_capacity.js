/**
 * read_train_capacity.js
 * يقرأ أقصى عدد جنود ممكن تدريبهم من واجهة اللعبة
 * 
 * الطريقة: نبحث في كلاسات Cocos2d عن الدالة المسؤولة عن حساب السعة
 * ونعترضها لقراءة القيمة
 */
'use strict';

// ابحث عن كل الكلاسات المتعلقة بالتدريب
Java.perform(function() {
    console.log("[*] جاري البحث عن كلاسات التدريب...");
    
    Java.enumerateLoadedClasses({
        onMatch: function(className) {
            var lower = className.toLowerCase();
            if (lower.indexOf('train') !== -1 || 
                lower.indexOf('army') !== -1 || 
                lower.indexOf('barrack') !== -1 ||
                lower.indexOf('recruit') !== -1) {
                console.log("  [class] " + className);
            }
        },
        onComplete: function() {
            console.log("[*] انتهى البحث عن الكلاسات.");
        }
    });
});
