// my_bot.js — يعتمد على game_api.js

var checkReady = setInterval(function() {
    if (Game && _ready) {
      
        console.log("\n🤖 البوت بدأ!");
        // جمع جميع موارد النظام
        Game.collectAll();
    }
}, 1000);
