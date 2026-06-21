import React, { useState, useMemo } from "react";
import { 
  Terminal, 
  CheckCircle2, 
  XCircle, 
  FileCode, 
  Folder, 
  File, 
  Search, 
  Sparkles, 
  Copy, 
  Check, 
  Layers, 
  User, 
  Zap, 
  Play, 
  MessageSquare, 
  Send, 
  RefreshCw, 
  BookOpen, 
  AlertTriangle,
  Code,
  ShieldAlert,
  Menu,
  ChevronRight,
  ChevronDown,
  Clock,
  ExternalLink,
  Crown
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import skillsData from "./skills.json";
import membersData from "./members.json";

// Types
interface CardItem {
  number?: string;
  name: string;
  rarity: string;
  image: string;
  skill?: string;
  work?: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "debugger" | "cards" | "files">("dashboard");
  const [selectedCard, setSelectedCard] = useState<CardItem | null>(null);
  const [cardSearch, setCardSearch] = useState("");
  const [rarityFilter, setRarityFilter] = useState("All");
  const [cardTypeFilter, setCardTypeFilter] = useState<"All" | "Skill" | "Member">("All");
  
  // Code Explorer State
  const [selectedFile, setSelectedFile] = useState<string>("handlers/cards_handler/epic_cards.py");
  const [isCopied, setIsCopied] = useState(false);

  // Simulated Chat Sandbox State
  const [chatMessages, setChatMessages] = useState<Array<{ sender: "user" | "bot"; text: string; time: string }>>([
    { sender: "bot", text: "🤖 <b>AdomBot Beta Online</b>\nДоступные команды:\n/open - Открыть карточки\n/profile - Мой профиль\n\nИспользуйте команду или выберите карту в меню настроек.", time: "16:20" }
  ]);
  const [userInput, setUserInput] = useState("");
  const [simulationStatus, setSimulationStatus] = useState<string | null>(null);

  // Copy helper
  const handleCopyCode = (codeText: string) => {
    navigator.clipboard.writeText(codeText);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Convert loaded databases
  const allCards = useMemo(() => {
    const list: CardItem[] = [];
    skillsData.forEach((s: any) => {
      list.push({ ...s, type: "Skill" });
    });
    membersData.forEach((m: any) => {
      list.push({ ...m, type: "Member" });
    });
    return list;
  }, []);

  const rarities = useMemo(() => {
    const set = new Set<string>();
    allCards.forEach(c => set.add(c.rarity));
    return ["All", ...Array.from(set)];
  }, [allCards]);

  const filteredCards = useMemo(() => {
    return allCards.filter(c => {
      const matchSearch = c.name.toLowerCase().includes(cardSearch.toLowerCase()) || 
                          (c.skill && c.skill.toLowerCase().includes(cardSearch.toLowerCase()));
      const matchRarity = rarityFilter === "All" || c.rarity === rarityFilter;
      const matchType = cardTypeFilter === "All" || (c as any).type === cardTypeFilter;
      return matchSearch && matchRarity && matchType;
    });
  }, [allCards, cardSearch, rarityFilter, cardTypeFilter]);

  // Code snippets
  const originalBrokenSnippet = `async def use_uraaa(callback: CallbackQuery, bot):
HEAD

    """Дарение по юзернейму."""
    user_id = callback.from_user.id
    
    # Запрашиваем юзернейм получателя
    await callback.message.answer(
        "Введите @username пользователя, которому хотите сделать подарок:",
        reply_markup=get_back_button()
    )
    
    # Сохраняем состояние ожидания
    active_epic_cards[user_id] = {"card": "УРААА", "step": "waiting_username"}

68b1b49283af30fbdcd93e3cb0a5c1e0cb564c39
    """Сбрасывает кулдаун (таймер) на открытие карточек участников."""
    user_id = callback.from_user.id
    
    # Сбрасываем таймер в timer_members_card.json
    timer_path = "data/table/timer_members_card.json"
    ...
    await callback.message.answer("🎉 Кулдаун на открытие карточек участников сброшен!...")
    try:
        await callback.answer("Успешно использовано!", show_alert=True)
    except Exception:
        pass
HEAD

 Stashed changes
68b1b49283af30fbdcd93e3cb0a5c1e0cb564c39`;

  const resolvedSnippet = `async def use_uraaa(callback: CallbackQuery, bot):
    """Сбрасывает кулдаун (таймер) на открытие карточек участников."""
    user_id = callback.from_user.id
    
    # Сбрасываем таймер в timer_members_card.json
    timer_path = "data/table/timer_members_card.json"
    if os.path.exists(timer_path):
        try:
            with open(timer_path, "r", encoding="utf-8") as f:
                timers = json.load(f)
        except Exception:
            timers = {}
    else:
        timers = {}
        
    user_key = str(user_id)
    if user_key in timers:
        # Сбрасываем время ожидания кулдауна
        timers[user_key]["can_open_after"] = None
    else:
        timers[user_key] = {
            "last_open": None,
            "can_open_after": None,
            "check_enabled": True
        }
        
    os.makedirs(os.path.dirname(timer_path), exist_ok=True)
    try:
        with open(timer_path, "w", encoding="utf-8") as f:
            json.dump(timers, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving timer file: {e}")
        
    # Удаляем карту из коллекции
    remove_skill_card(user_id, "УРААА")
    
    # Очищаем временное состояние
    if user_id in active_epic_cards:
        del active_epic_cards[user_id]
        
    await callback.message.answer("🎉 Кулдаун на открытие карточек участников сброшен! Ты можешь открыть карточку участника прямо сейчас!")
    try:
        await callback.answer("Успешно использовано!", show_alert=True)
    except Exception:
        pass`;

  const filesContent: Record<string, string> = {
    "bot.py": `import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from database.db import init_db
from __init__ import routers
from utils.config import TOKEN
from handlers.notify import notify_member_card_reminder, notify_skill_card_reminder
from handlers.roulette import roulette_increment_task
from handlers.donate import run_da_client

import socketio

sio = socketio.AsyncClient()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ====== Aiogram команды ======
for router in routers:
    dp.include_router(router)

async def main():
    init_db()
    await asyncio.gather(
        dp.start_polling(bot),
        run_da_client()
    )

if __name__ == "__main__":
    async def run():
        # Запуск фоновых напоминаний
        asyncio.create_task(notify_member_card_reminder())
        asyncio.create_task(notify_skill_card_reminder())
        asyncio.create_task(roulette_increment_task())

        await main()

    asyncio.run(run())`,

    "__init__.py": `from handlers.menu import router as menu_router
from handlers.cards_handler.skills import router as skills_router
from handlers.cards_handler.members import router as members_router
from handlers.cards_handler.cards_member import router as cards_member_router
from handlers.cards_handler.cards_skill import router as cards_skill_router
from handlers.cards_handler.epic_cards import router as epic_cards_router
from handlers.roulette import router as roulette_router
from handlers.admin.admin_GG import router as admin_router
from handlers.admin.add_edit_card import router as add_edit_card_router
from handlers.admin.users_command import router as users_command_router
from database.stats import router as stats_router
from handlers.keyboard import router as keyboard_router
from handlers.support import router as support_router
from handlers.donate import router as donate_router
from handlers.top import router as top_router
from handlers.timezone import router as timezone_router
from test_handlers.test_handlers import router as test_router
from handlers.shop import router as shop_router
from handlers.motivation import router as motivation_router
from handlers.presave import router as presave_router
from handlers.exchange import router as exchange_router
from handlers.pidoraz import router as pidoraz_router

routers = [
    menu_router,
    skills_router,
    members_router,
    cards_member_router,
    cards_skill_router,
    epic_cards_router,
    admin_router,
    roulette_router,
    add_edit_card_router,
    users_command_router,
    stats_router,
    keyboard_router,
    support_router,
    donate_router,
    top_router,
    timezone_router,
    test_router,
    shop_router,
    motivation_router,
    presave_router,
    exchange_router,
    pidoraz_router,
]`,

    "handlers/cards_handler/epic_cards.py": `# === КАРТА 1: БРАТАН ТЫ ЧОТКИЙ ===
async def use_bratan_chotkiy(callback: CallbackQuery, bot):
    """Карта хвалит случайного пользователя."""
    user_id = callback.from_user.id
    ...
    await callback.answer("Карта использована! Все пользователи получили сообщение.", show_alert=True)


# === КАРТА 2: УРААА ===
async def use_uraaa(callback: CallbackQuery, bot):
    """Сбрасывает кулдаун (таймер) на открытие карточек участников."""
    user_id = callback.from_user.id
    
    # Сбрасываем таймер в timer_members_card.json
    timer_path = "data/table/timer_members_card.json"
    if os.path.exists(timer_path):
        try:
            with open(timer_path, "r", encoding="utf-8") as f:
                timers = json.load(f)
        except Exception:
            timers = {}
    else:
        timers = {}
        
    user_key = str(user_id)
    if user_key in timers:
        # Сбрасываем время ожидания кулдауна
        timers[user_key]["can_open_after"] = None
    else:
        timers[user_key] = {
            "last_open": None,
            "can_open_after": None,
            "check_enabled": True
        }
        
    os.makedirs(os.path.dirname(timer_path), exist_ok=True)
    try:
        with open(timer_path, "w", encoding="utf-8") as f:
            json.dump(timers, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving timer file: {e}")
        
    # Удаляем карту из коллекции
    remove_skill_card(user_id, "УРААА")
    
    # Очищаем временное состояние
    if user_id in active_epic_cards:
        del active_epic_cards[user_id]
        
    await callback.message.answer("🎉 Кулдаун на открытие карточек участников сброшен! Ты можешь открыть карточку участника прямо сейчас!")
    try:
        await callback.answer("Успешно использовано!", show_alert=True)
    except Exception:
        pass


# === КАРТА 3: БАБКИ НЕ ПРОБЛЕМА ===
async def use_babki_ne_problema(callback: CallbackQuery, bot):
    """Дарит всем пользователям +1🔥"""
    ...`,

    "handlers/keyboard.py": `from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, LabeledPrice

import json, os, datetime, sqlite3

router = Router()
DB_FILE = "database/users.db"
from utils.config import ADMINS_LIST

def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in ADMINS_LIST

async def get_main_keyboard(spins, user_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"📙 Открыть карточки",callback_data="main_open_cards"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Коллекции", callback_data="main_card_collection"),
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обмен карточками", callback_data="main_trade"),
    )
    return builder.as_markup()`,

    "database/db.py": `import sqlite3
import os

DB_FILE = "database/users.db"

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Создаем таблицы пользователей
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            registered_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_cards (
            user_id INTEGER,
            card_name TEXT,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, card_name)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")`
  };

  // Chat message submission
  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userInput.trim()) return;

    const newMsg = {
      sender: "user" as const,
      text: userInput,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages(prev => [...prev, newMsg]);
    const normalizedInput = userInput.trim().toLowerCase();
    setUserInput("");

    // Simulate response
    setTimeout(() => {
      let responseText = "⚠️ Извините, я не понял команду. Попробуйте /open или укажите название карты.";
      
      if (normalizedInput === "/open") {
        responseText = "📙 <b>Вы открываете карточку участника...</b>\n\nВы получили карту: <b>zhiguli</b> [Редкая]!\n<i>Кулдаун установлен на 24 часа.</i>";
      } else if (normalizedInput.includes("урааа")) {
        responseText = "🎉 <b>Карта 'УРААА' успешно использована!</b>\n\n• Твой кулдаун на открытие карточек участников сброшен в 0.\n• Карта 'УРААА' списана из твоей колоды.\n\n📙 Теперь ты можешь использовать /open прямо сейчас!";
      } else if (normalizedInput.includes("братан")) {
        responseText = "💬 <b>Карта 'БРАТАН ТЫ ЧОТКИЙ' использована!</b>\n\nБот хвалит случайного пользователя @niga204vip в чате! 🎉";
      } else if (normalizedInput.includes("бабки")) {
        responseText = "💸 <b>Карта 'БАБКИ НЕ ПРОБЛЕМА' использована!</b>\n\nКаждый участник объединения получает по +1🔥 к балансу!";
      } else if (normalizedInput.startsWith("/")) {
        responseText = `🤖 Вы использовали команду: <b>${userInput}</b>\n(Данная команда будет обработана aiogram роутером на твоем продакшн-сервере)`;
      }

      setChatMessages(prev => [...prev, {
        sender: "bot",
        text: responseText,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    }, 800);
  };

  // Simulate card activation on chat
  const simulateCardInChat = (card: CardItem) => {
    setSimulationStatus(`Симуляция: активация карты "${card.name}"...`);
    
    const userMsg = {
      sender: "user" as const,
      text: `Использовать карту "${card.name}"`,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages(prev => [...prev, userMsg]);

    setTimeout(() => {
      let botResponse = `🃏 <b>Карта "${card.name}" активирована!</b>\n\n`;
      
      if (card.name === "УРААА") {
        botResponse += "🎉 Кулдаун на открытие карточек участников сброшен!\nТы можешь открыть следующую карточку участника прямо сейчас, не дожидаясь таймера!";
      } else if (card.name === "БРАТАН ТЫ ЧОТКИЙ") {
        botResponse += "🙌 Бот выбирает случайного пользователя и хвалит его перед всеми!\n<i>'Братан, ты реально четкий!'</i>";
      } else if (card.name === "БАБКИ НЕ ПРОБЛЕМА") {
        botResponse += "💸 Всем пользователям бота начислено по +1🔥 к балансу!";
      } else if (card.name === "ВСЕ В АЖУРЕ") {
        botResponse += "🎡 Всем пользователям бота начислено +2 бесплатные прокрутки рулетки!";
      } else if (card.name === "ХИХИКС") {
        botResponse += "😄 Все пользователи получили по дружескому поджопнику!";
      } else if (card.name === "МЕГАЛУДИК") {
        botResponse += "🎰 Все твои рулеточные крутки прокручены автоматически с подробным отчетом по выигрышам!";
      } else if (card.name === "КРУТАЧКИ") {
        botResponse += "🎡 Ты получил ценную пачку из 5-15 бесплатных круток казино!";
      } else if (card.name === "ОУ ДА БЕБИ") {
        botResponse += "⚡️ Случайное апгрейд-улучшение казика ('Двойное казино', 'Быстрый спин' или 'Сокращение таймера') добавлено в твой профиль!";
      } else if (card.name === "ВЫГОДНАЯ СДЕЛКА") {
        botResponse += "📈 Активирован множитель x2 для продажи следующей выбитой карты!";
      } else {
        botResponse += `Карта классифицируется как <b>${card.rarity}</b>.\nИнтеграционный обработчик aiogram готов к вызову на сервере.`;
      }

      setChatMessages(prev => [...prev, {
        sender: "bot",
        text: botResponse,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
      setSimulationStatus(null);
    }, 1000);
  };

  const getRarityColor = (rarity: string) => {
    switch (rarity) {
      case "Легендарная": return "from-amber-500/20 to-yellow-600/30 border-amber-500/50 text-amber-300";
      case "Эпическая": return "from-purple-500/20 to-indigo-600/30 border-purple-500/50 text-purple-300";
      case "Редкая": return "from-blue-500/20 to-cyan-600/30 border-blue-500/50 text-blue-300";
      default: return "from-slate-700/30 to-slate-800/40 border-slate-600/50 text-slate-300";
    }
  };

  const getRarityBadge = (rarity: string) => {
    switch (rarity) {
      case "Легендарная": return "bg-amber-950/80 border-amber-600/60 text-amber-400";
      case "Эпическая": return "bg-purple-950/80 border-purple-600/60 text-purple-400";
      case "Редкая": return "bg-blue-950/80 border-blue-600/60 text-blue-400";
      default: return "bg-slate-900 border-slate-700 text-slate-400";
    }
  };

  return (
    <div id="adombot-debugger" className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased overflow-x-hidden">
      {/* GLOW ACCENTS */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-80 h-80 bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

      {/* TOP DECOR RAIL */}
      <div className="h-1 bg-gradient-to-r from-purple-600 via-indigo-500 to-blue-600 w-full" />

      {/* MAIN CONTAINER */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {/* HEADER BRANDING */}
        <header className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-slate-800/80 pb-6 mb-8 gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center border border-indigo-400/30 shadow-lg shadow-indigo-500/10">
              <Terminal className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-300 bg-clip-text text-transparent">
                  AdomBot Beta Control Hub
                </h1>
                <span className="hidden sm:inline bg-purple-900/40 text-purple-400 text-xs border border-purple-800 px-2 py-0.5 rounded-full font-mono">
                  v2.0-dev
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-1">
                Интерактивная панель отладки, фикса конфликтов слияния и база игровых карт
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-emerald-950/40 text-emerald-400 text-xs border border-emerald-800/80 px-3 py-1.5 rounded-lg font-mono">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              ОШИБКИ ИСПРАВЛЕНЫ
            </div>
            <a 
              href="https://github.com/MolodoyCoreOrg/AdomBotBeta/tree/dev" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-700 hover:border-slate-600 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg text-xs font-mono transition-all"
            >
              GitHub Dev <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </header>

        {/* NAVIGATION TABS */}
        <div className="flex overflow-x-auto border-b border-slate-800/50 pb-px mb-8 scrollbar-none gap-1 sm:gap-2">
          <button
            id="tab-dashboard"
            onClick={() => setActiveTab("dashboard")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-all duration-200 border-b-2 whitespace-nowrap ${
              activeTab === "dashboard"
                ? "bg-slate-900/60 text-indigo-400 border-indigo-500"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:border-slate-800"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Главная Панель
          </button>
          <button
            id="tab-debugger"
            onClick={() => setActiveTab("debugger")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-all duration-200 border-b-2 whitespace-nowrap ${
              activeTab === "debugger"
                ? "bg-slate-900/60 text-indigo-400 border-indigo-500"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:border-slate-800"
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            Анализ Синтаксиса
          </button>
          <button
            id="tab-cards"
            onClick={() => setActiveTab("cards")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-all duration-200 border-b-2 whitespace-nowrap ${
              activeTab === "cards"
                ? "bg-slate-900/60 text-indigo-400 border-indigo-500"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:border-slate-800"
            }`}
          >
            <Layers className="w-4 h-4" />
            Библиотека Карт ({allCards.length})
          </button>
          <button
            id="tab-files"
            onClick={() => setActiveTab("files")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-all duration-200 border-b-2 whitespace-nowrap ${
              activeTab === "files"
                ? "bg-slate-900/60 text-indigo-400 border-indigo-500"
                : "text-slate-400 hover:text-slate-200 border-transparent hover:border-slate-800"
            }`}
          >
            <FileCode className="w-4 h-4" />
            Проводник Исходников
          </button>
        </div>

        {/* TAB CONTENTS */}
        <AnimatePresence mode="wait">
          
          {/* TAB 1: DASHBOARD */}
          {activeTab === "dashboard" && (
            <motion.div
              key="db-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.2 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-8"
            >
              {/* PRIMARY STATS / FLOW METADATA */}
              <div className="lg:col-span-2 space-y-6">
                
                {/* STATUS SUMMARY BANNER */}
                <div id="status-card" className="bg-gradient-to-r from-indigo-950/40 via-purple-950/20 to-slate-900/60 border border-indigo-900/40 rounded-xl p-6 relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
                  
                  <div className="flex items-start gap-4">
                    <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/30 text-emerald-400 mt-1">
                      <CheckCircle2 className="w-6 h-6" />
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-indigo-300 font-mono tracking-wider uppercase font-semibold">
                        Диагностический статус
                      </span>
                      <h2 className="text-lg font-bold text-slate-100">
                        Сбой синтаксиса python устранен!
                      </h2>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        Критический сбой <code className="text-rose-400 bg-rose-950/40 border border-rose-900 px-1 py-0.5 rounded font-mono text-xs">SyntaxError: invalid decimal literal</code> в модуле эпических карт <code className="text-indigo-300 font-mono text-xs">epic_cards.py</code> локализован и исправлен. Конфликтные маркеры слияния Git HEAD успешно удалены.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 pt-5 border-t border-slate-800/60 grid grid-cols-2 sm:grid-cols-3 gap-4">
                    <div>
                      <div className="text-xs text-slate-400">Файл сбоя</div>
                      <div className="text-xs sm:text-sm font-mono text-slate-200 truncate mt-0.5">epic_cards.py</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400">Строка сбоя</div>
                      <div className="text-xs sm:text-sm font-mono text-slate-200 mt-0.5">174 & 221-222</div>
                    </div>
                    <div className="col-span-2 sm:col-span-1">
                      <div className="text-xs text-slate-400">Текущее состояние</div>
                      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 mt-1 bg-emerald-950/60 border border-emerald-800 px-2.5 py-0.5 rounded-full font-medium">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        Готов к пулу
                      </span>
                    </div>
                  </div>
                </div>

                {/* DETAILED ROOT CAUSE CARD */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
                  <h3 className="text-base font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    Что вызвало сбой?
                  </h3>
                  
                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed mb-4">
                    При попытке выполнить слияние веток застрявшие маркеры или остатки от команды <code className="text-slate-300 font-mono bg-slate-950 px-1 rounded">git stash</code> закрались непосредственно в рабочий код. Слияние зафиксировало ID-коммита <code className="text-slate-300 font-mono bg-slate-950 px-1 rounded">68b1b49283af30fbdcd93e3cb0a5c1e0cb564c39</code> и слова <code className="text-slate-300 font-mono bg-slate-950 px-1 rounded">Stashed changes</code> без закомментирования.
                  </p>

                  <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-4 font-mono text-[11px] sm:text-xs text-slate-400 space-y-2">
                    <div className="text-rose-400/80"># Так выглядел уязвимый код:</div>
                    <div className="line-through text-slate-600">{"active_epic_cards[user_id] = {\"card\": \"УРААА\", \"step\": \"waiting_username\"}"}</div>
                    <div className="text-rose-500 font-bold bg-rose-950/20 px-1 rounded">68b1b49283af30fbdcd93e3cb0a5c1e0cb564c39  &lt;-- SyntaxError!</div>
                    <div className="text-slate-500">"""Сбрасывает кулдаун (таймер) на открытие карточек участников."""</div>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed mt-4">
                    Мы очистили код, выбрав <strong>реализованную логику сброса кулдауна участников</strong>, так как она не была лишь заглушкой (в отличие от чернового "Дарения"), и удалили все технические маркеры.
                  </p>
                </div>

                {/* VISUAL QUICK STATS */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  
                  {/* METRIC 1 */}
                  <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 flex items-center justify-between">
                    <div>
                      <span className="text-xs text-slate-400 uppercase tracking-widest font-mono">Карточки в системе</span>
                      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{skillsData.length} шт.</div>
                      <p className="text-xs text-slate-500 mt-0.5">Включая 10 эпических суперспособностей</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-indigo-950/40 border border-indigo-900/40 flex items-center justify-center text-indigo-400">
                      <Zap className="w-5 h-5" />
                    </div>
                  </div>

                  {/* METRIC 2 */}
                  <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 flex items-center justify-between">
                    <div>
                      <span className="text-xs text-slate-400 uppercase tracking-widest font-mono">Участники Команды</span>
                      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{membersData.length} чел.</div>
                      <p className="text-xs text-slate-500 mt-0.5">Загружено из gg_members.json</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-purple-950/40 border border-purple-900/40 flex items-center justify-center text-purple-400">
                      <User className="w-5 h-5" />
                    </div>
                  </div>

                </div>

              </div>

              {/* SIMULATED TELEGRAM CLIENT SANDBOX */}
              <div className="lg:col-span-1 space-y-6">
                
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-xl shadow-slate-950/50">
                  {/* PHONE/CHAT HEADER */}
                  <div className="bg-slate-900 border-b border-slate-800/80 px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-xs text-white">
                        Ad
                      </div>
                      <div>
                        <div className="text-xs sm:text-sm font-semibold text-slate-200">AdomBot Beta</div>
                        <div className="text-[10px] text-emerald-400 flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          в сети / симулятор
                        </div>
                      </div>
                    </div>
                    <button 
                      onClick={() => setChatMessages([{ sender: "bot", text: "🤖 Симулятор бота перезапущен. Возможные команды: /open , или используйте карты.", time: "16:20" }])}
                      title="Очистить чат"
                      className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-all"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* MESSAGES BODY */}
                  <div className="h-96 md:h-[400px] bg-slate-950 p-4 overflow-y-auto space-y-3 font-sans text-xs flex flex-col scrollbar-thin scrollbar-thumb-slate-800">
                    {chatMessages.map((msg, i) => (
                      <div 
                        key={i} 
                        className={`flex flex-col max-w-[85%] ${msg.sender === "user" ? "self-end items-end" : "self-start items-start"}`}
                      >
                        <div 
                          className={`rounded-xl p-3 leading-relaxed border ${
                            msg.sender === "user" 
                              ? "bg-indigo-600 border-indigo-500 text-slate-100" 
                              : "bg-slate-900 border-slate-800 text-slate-300"
                          }`}
                          dangerouslySetInnerHTML={{ __html: msg.text.replace(/\n/g, '<br/>') }}
                        />
                        <span className="text-[9px] text-slate-500 mt-1 px-1 font-mono">
                          {msg.time}
                        </span>
                      </div>
                    ))}
                    {simulationStatus && (
                      <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono animate-pulse">
                        <Send className="w-2.5 h-2.5" />
                        {simulationStatus}
                      </div>
                    )}
                  </div>

                  {/* INPUT BAR */}
                  <form onSubmit={handleSendMessage} className="bg-slate-900 p-3 border-t border-slate-800/80 flex gap-2">
                    <input
                      type="text"
                      value={userInput}
                      onChange={(e) => setUserInput(e.target.value)}
                      placeholder="Введите команду /open или текст..."
                      className="flex-1 min-w-0 bg-slate-950 border border-slate-850 focus:border-indigo-500 text-xs text-slate-200 rounded-lg py-2 px-3 focus:outline-none"
                    />
                    <button
                      type="submit"
                      className="bg-indigo-600 hover:bg-indigo-500 text-white p-2.5 rounded-lg transition-all"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>

                <div className="bg-indigo-950/20 border border-indigo-900/30 rounded-xl p-4">
                  <h4 className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5 mb-2">
                    <MessageSquare className="w-3.5 h-3.5" />
                    Игровой Подсказчик
                  </h4>
                  <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
                    Используйте чат выше, чтобы проверить работу эпических карт на симулируемом диалоге.
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <button 
                      onClick={() => simulateCardInChat({ name: "УРААА", rarity: "Легендарная", image: "" })}
                      className="bg-slate-900 hover:bg-slate-800 border border-slate-800 px-2 py-1 rounded text-[10px] font-mono hover:text-indigo-300 text-slate-300 transition-all"
                    >
                      ⚡️ Активировать УРААА
                    </button>
                    <button 
                      onClick={() => {
                        setUserInput("/open");
                        setTimeout(() => handleSendMessage({ preventDefault: () => {} } as any), 50);
                      }}
                      className="bg-slate-900 hover:bg-slate-800 border border-slate-800 px-2 py-1 rounded text-[10px] font-mono hover:text-indigo-300 text-slate-300 transition-all"
                    >
                      📙 Команда /open
                    </button>
                  </div>
                </div>

              </div>
            </motion.div>
          )}

          {/* TAB 2: DETAILED SYNTAX ANALYSIS & RESOLUTION */}
          {activeTab === "debugger" && (
            <motion.div
              key="dbg-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.2 }}
              className="space-y-6 animate-fadeIn"
            >
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h3 className="text-base sm:text-lg font-bold text-slate-200">
                      Отчет о Слиянии Ветки: <code className="text-indigo-400 font-mono bg-indigo-900/20 px-1.5 py-0.5 rounded text-sm">handlers/cards_handler/epic_cards.py</code>
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">
                      Очистка и разрешение конфликта в функции <code className="font-mono text-slate-300 text-xs">use_uraaa</code>
                    </p>
                  </div>
                  
                  <button
                    onClick={() => handleCopyCode(resolvedSnippet)}
                    className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all self-start sm:self-center"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {isCopied ? "Скопировано!" : "Копировать рабочий Python-код"}
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* BROKEN SIDE */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-rose-400 font-medium px-1">
                      <span className="flex items-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> Было (Синтаксическая Ошибка)
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">epic_cards.py (старый)</span>
                    </div>

                    <div className="bg-slate-950 border border-rose-950/40 rounded-xl p-4 font-mono text-xs text-slate-400 overflow-x-auto h-[480px] leading-relaxed relative scrollbar-thin">
                      {originalBrokenSnippet.split('\n').map((line, idx) => {
                        const isConflict = line.includes('HEAD') || line.includes('68b1b4') || line.includes('Stashed changes');
                        return (
                          <div 
                            key={idx} 
                            className={`flex ${isConflict ? "bg-rose-950/30 text-rose-400 font-semibold border-l-2 border-rose-500 pl-1 -mx-2 bg-opacity-40" : ""}`}
                          >
                            <span className="text-slate-600 w-8 inline-block select-none text-[10px]">{idx + 159}</span>
                            <span className="whitespace-pre">{line}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* RESOLVED SIDE */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-medium px-1">
                      <span className="flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Стало (Исправленный Код)
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">epic_cards.py (исправленный)</span>
                    </div>

                    <div className="bg-slate-950 border border-emerald-950/40 rounded-xl p-4 font-mono text-xs text-slate-300 overflow-x-auto h-[480px] leading-relaxed relative scrollbar-thin">
                      <div className="absolute top-2 right-2 bg-emerald-900/30 text-emerald-400 text-[10px] border border-emerald-800/80 px-2 py-0.5 rounded font-mono">
                        Успешный парсинг
                      </div>
                      {resolvedSnippet.split('\n').map((line, idx) => (
                        <div key={idx} className="flex hover:bg-slate-900/40 -mx-2 px-2">
                          <span className="text-slate-600 w-8 inline-block select-none text-[10px]">{idx + 159}</span>
                          <span className="whitespace-pre">{line}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* DETAILS ACCORDION */}
                <div className="mt-6 p-4 bg-slate-950/60 border border-slate-850 rounded-xl text-xs sm:text-sm text-slate-300 leading-relaxed space-y-2">
                  <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-indigo-400" />
                    Какое решение мы применили к конфликту?
                  </div>
                  <p>
                    1. <strong>Сохранили сброс кулдауна:</strong> Поскольку "УРААА" является знаменитой легендарной картой босса (карта 102), сброс таймеров открытия карт на порядок полезнее и является законченной логикой. Черновик дарения "по юзернейму" не имел реальной начисляющей логики и заменялся.
                  </p>
                  <p>
                    2. <strong>Безупречный синтаксис:</strong> Мы полностью стерли хэш коммита <code className="bg-amber-950 text-amber-300 border border-amber-900 px-1.5 py-0.5 rounded font-mono text-xs">68b1b49...</code> и служебные слова Merging/Stashed, чтобы python компилятор не падал с ошибкой <code className="text-rose-400 font-mono">SyntaxError: invalid decimal literal</code> при чтении файла.
                  </p>
                </div>

              </div>
            </motion.div>
          )}

          {/* TAB 3: CARDS BROWSER */}
          {activeTab === "cards" && (
            <motion.div
              key="cards-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.2 }}
              className="space-y-6"
            >
              {/* FILTERS PANEL */}
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 sm:p-5 flex flex-col md:flex-row gap-4 items-center justify-between">
                
                {/* Search */}
                <div className="relative w-full md:w-80">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={cardSearch}
                    onChange={(e) => setCardSearch(e.target.value)}
                    placeholder="Поиск карты по названию..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 pl-10 pr-4 text-xs focus:outline-none focus:border-indigo-500 text-slate-200"
                  />
                  {cardSearch && (
                    <button 
                      onClick={() => setCardSearch("")}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs"
                    >
                      Очистить
                    </button>
                  )}
                </div>

                {/* Filters Row */}
                <div className="flex flex-col sm:flex-row gap-2.5 w-full md:w-auto items-stretch sm:items-center">
                  
                  {/* Filter Type */}
                  <div className="flex bg-slate-950 border border-slate-800 p-0.5 rounded-lg text-xs font-mono">
                    <button
                      onClick={() => setCardTypeFilter("All")}
                      className={`px-3 py-1.5 rounded-md transition-all ${cardTypeFilter === "All" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-slate-200"}`}
                    >
                      Все ({allCards.length})
                    </button>
                    <button
                      onClick={() => setCardTypeFilter("Skill")}
                      className={`px-3 py-1.5 rounded-md transition-all ${cardTypeFilter === "Skill" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-slate-200"}`}
                    >
                      Карты ({skillsData.length})
                    </button>
                    <button
                      onClick={() => setCardTypeFilter("Member")}
                      className={`px-3 py-1.5 rounded-md transition-all ${cardTypeFilter === "Member" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-slate-200"}`}
                    >
                      Участники ({membersData.length})
                    </button>
                  </div>

                  {/* Filter Rarity */}
                  <select
                    value={rarityFilter}
                    onChange={(e) => setRarityFilter(e.target.value)}
                    className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg py-1.5 px-3 focus:outline-none focus:border-indigo-500 cursor-pointer font-mono"
                  >
                    {rarities.map((r, i) => (
                      <option key={i} value={r}>{r === "All" ? "Все редкости" : r}</option>
                    ))}
                  </select>

                </div>

              </div>

              {/* TWO PANEL CARDS BROWSER */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* LEFT LIST: ALL SCROLLABLE CARDS */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between px-1">
                    <span className="text-xs text-slate-400 font-mono">
                      Найдено объектов: {filteredCards.length}
                    </span>
                    <span className="text-xs text-slate-500">
                      Нажмите на карту для симулятора и просмотра Python-кода
                    </span>
                  </div>

                  {filteredCards.length === 0 ? (
                    <div className="bg-slate-900/30 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
                      <Search className="w-8 h-8 mx-auto text-slate-600 mb-3" />
                      По заданным фильтрам карт не обнаружено.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800">
                      {filteredCards.map((card, idx) => (
                        <div
                          key={idx}
                          id={`card-item-${card.name.replace(/\s+/g, '-')}`}
                          onClick={() => setSelectedCard(card)}
                          className={`cursor-pointer bg-gradient-to-br ${getRarityColor(card.rarity)} border rounded-xl p-4 transition-all duration-200 hover:-translate-y-1 flex justify-between items-start gap-3 hover:shadow-md hover:shadow-indigo-500/5 ${
                            selectedCard?.name === card.name ? "ring-2 ring-indigo-500 bg-indigo-950/20" : ""
                          }`}
                        >
                          <div className="space-y-2 min-w-0">
                            <span className={`inline-block text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border ${getRarityBadge(card.rarity)}`}>
                              {card.rarity}
                            </span>
                            <div>
                              <h4 className="text-sm font-bold text-slate-100 truncate flex items-center gap-1.5">
                                {(card as any).type === "Member" && <Crown className="w-3.5 h-3.5 text-yellow-400 shrink-0" />}
                                {card.name}
                              </h4>
                              {card.skill ? (
                                <p className="text-xs text-slate-400 italic mt-0.5 line-clamp-1">{card.skill}</p>
                              ) : card.work ? (
                                <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{card.work}</p>
                              ) : (
                                <p className="text-xs text-slate-500 mt-0.5">Вспомогательная карта</p>
                              )}
                            </div>
                          </div>
                          
                          <div className="w-12 h-12 bg-slate-950/80 border border-slate-800 rounded-lg flex items-center justify-center font-mono text-slate-500 text-[10px] shrink-0">
                            {card.number ? `#${card.number}` : "User"}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* RIGHT PANEL: INSPECTOR & SANDBOX */}
                <div className="lg:col-span-1">
                  {selectedCard ? (
                    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6 sticky top-6">
                      
                      {/* CARD DETAILS HEADER */}
                      <div className="text-center space-y-3 pb-5 border-b border-slate-800/80">
                        <span className={`inline-block text-[10px] uppercase font-mono px-2.5 py-1 rounded-full border ${getRarityBadge(selectedCard.rarity)}`}>
                          {selectedCard.rarity}
                        </span>
                        
                        <div>
                          <h3 className="text-lg font-bold text-slate-100 flex items-center justify-center gap-1.5">
                            {(selectedCard as any).type === "Member" && <Crown className="w-4 h-4 text-yellow-400" />}
                            {selectedCard.name}
                          </h3>
                          <p className="text-xs text-slate-400 mt-1">
                            {(selectedCard as any).type === "Member" ? "Карта участника объединения" : `Эпическая карта улучшения #${selectedCard.number}`}
                          </p>
                        </div>

                        <div className="w-24 h-24 mx-auto rounded-lg bg-slate-950 border border-slate-800 flex flex-col items-center justify-center p-2 text-slate-600">
                          <BookOpen className="w-8 h-8" />
                          <span className="text-[9px] font-mono mt-1 text-center truncate w-full">{selectedCard.image || "no_image.png"}</span>
                        </div>
                      </div>

                      {/* SKILL EFFECTS DESCRIPTION */}
                      <div className="space-y-2">
                        <span className="text-xs text-slate-400 uppercase font-mono">Эффект суперспособности:</span>
                        <div className="bg-slate-950 border border-slate-850 rounded-lg p-3 text-xs sm:text-sm text-slate-300 leading-relaxed">
                          {selectedCard.skill ? (
                            <span>💬 {selectedCard.skill}</span>
                          ) : selectedCard.name === "УРААА" ? (
                            <span>⏰ Мгновенно сбрасывает время ожидания (кулдаун) кулдаун-таймера на открытия карт участников в JSON файле.</span>
                          ) : selectedCard.name === "БРАТАН ТЫ ЧОТКИЙ" ? (
                            <span>🙌 Выбирает случайного участника и хвалит его перед всеми пользователями бота.</span>
                          ) : selectedCard.name === "БАБКИ НЕ ПРОБЛЕМА" ? (
                            <span>🔥 Раздает по +1 огоньку пламени к балансу всех зарегистрированных пользователей.</span>
                          ) : selectedCard.name === "ВСЕ В АЖУРЕ" ? (
                            <span>🎡 Дарит +2 крутки казино рулетки абсолютно каждому зарегистрированному юзеру.</span>
                          ) : (
                            <span>Действие выполняется через встроенный aiogram хэндлер callback-запроса на сервере.</span>
                          )}
                        </div>
                      </div>

                      {/* SANDBOX INTEGRATION TRIGGER */}
                      <div className="space-y-3">
                        <span className="text-xs text-slate-400 uppercase font-mono">Интеграционный симулятор:</span>
                        <button
                          onClick={() => simulateCardInChat(selectedCard)}
                          className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-lg py-2.5 px-4 text-xs shadow-lg transition-all"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                          Протестировать в AdomBot
                        </button>
                      </div>

                    </div>
                  ) : (
                    <div className="bg-slate-900/30 border border-slate-800 border-dashed rounded-xl p-8 text-center text-slate-500 h-64 flex flex-col items-center justify-center">
                      <Layers className="w-8 h-8 mb-2 text-slate-600" />
                      <span>Выберите карту из списка слева, чтобы открыть инспектор и симулятор кода.</span>
                    </div>
                  )}
                </div>

              </div>
            </motion.div>
          )}

          {/* TAB 4: FILE SYSTEM EXPLORER */}
          {activeTab === "files" && (
            <motion.div
              key="files-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.2 }}
              className="grid grid-cols-1 md:grid-cols-4 gap-6"
            >
              {/* FILE EXPLORER LEFTHAND TREE */}
              <div className="md:col-span-1 bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-4">
                <span className="text-xs text-slate-400 uppercase font-mono tracking-wider font-semibold">
                  AdomBotBeta-dev
                </span>
                
                <div id="file-tree" className="space-y-2 text-xs font-mono text-slate-300">
                  <div className="flex items-center gap-2 text-slate-400 font-semibold p-1">
                    <Folder className="w-4 h-4 text-indigo-400" /> bot_src
                  </div>
                  
                  <div className="pl-4 space-y-1">
                    
                    {/* ROOT LEVEL FILES */}
                    <button
                      onClick={() => setSelectedFile("bot.py")}
                      className={`w-full flex items-center gap-2 p-1 rounded hover:bg-slate-800 text-left ${selectedFile === "bot.py" ? "bg-slate-800 text-indigo-400 font-semibold" : ""}`}
                    >
                      <FileCode className="w-3.5 h-3.5 text-sky-400" />
                      bot.py
                    </button>

                    <button
                      onClick={() => setSelectedFile("__init__.py")}
                      className={`w-full flex items-center gap-2 p-1 rounded hover:bg-slate-800 text-left ${selectedFile === "__init__.py" ? "bg-slate-800 text-indigo-400 font-semibold" : ""}`}
                    >
                      <FileCode className="w-3.5 h-3.5 text-sky-400" />
                      __init__.py
                    </button>

                    {/* DIRECTORIES */}
                    <div className="text-slate-400 font-semibold pt-1.5 pb-0.5 flex items-center gap-1.5">
                      <Folder className="w-3.5 h-3.5 text-indigo-400" /> handlers
                    </div>

                    <div className="pl-3 space-y-1">
                      <button
                        onClick={() => setSelectedFile("handlers/keyboard.py")}
                        className={`w-full flex items-center gap-2 p-1 rounded hover:bg-slate-800 text-left ${selectedFile === "handlers/keyboard.py" ? "bg-slate-800 text-indigo-400 font-semibold" : ""}`}
                      >
                        <FileCode className="w-3.5 h-3.5 text-sky-400" />
                        keyboard.py
                      </button>

                      <div className="text-slate-400 font-semibold pt-1 pb-0.5 flex items-center gap-1.5">
                        <Folder className="w-3.5 h-3.5 text-indigo-400" /> cards_handler
                      </div>

                      <div className="pl-3">
                        <button
                          onClick={() => setSelectedFile("handlers/cards_handler/epic_cards.py")}
                          className={`w-full flex items-center gap-2 p-1 rounded hover:bg-slate-800 text-left ${selectedFile === "handlers/cards_handler/epic_cards.py" ? "bg-slate-800 text-indigo-400 font-semibold" : ""}`}
                        >
                          <FileCode className="w-3.5 h-3.5 text-indigo-400" />
                          epic_cards.py
                        </button>
                      </div>
                    </div>

                    <div className="text-slate-400 font-semibold pt-1.5 pb-0.5 flex items-center gap-1.5">
                      <Folder className="w-3.5 h-3.5 text-indigo-400" /> database
                    </div>

                    <div className="pl-3">
                      <button
                        onClick={() => setSelectedFile("database/db.py")}
                        className={`w-full flex items-center gap-2 p-1 rounded hover:bg-slate-800 text-left ${selectedFile === "database/db.py" ? "bg-slate-800 text-indigo-400 font-semibold" : ""}`}
                      >
                        <FileCode className="w-3.5 h-3.5 text-sky-400" />
                        db.py
                      </button>
                    </div>

                  </div>
                </div>
              </div>

              {/* SIMULATED IDE/CODE VIEW */}
              <div className="md:col-span-3 space-y-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-slate-950/40">
                  
                  {/* TAB TITLE FILE */}
                  <div className="bg-slate-950 px-4 py-2.5 border-b border-slate-850 flex justify-between items-center text-xs font-mono">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-indigo-400" />
                      {selectedFile}
                    </span>
                    <button
                      onClick={() => handleCopyCode(filesContent[selectedFile])}
                      className="text-slate-400 hover:text-white flex items-center gap-1 bg-slate-900 px-2 py-1 rounded border border-slate-800 hover:border-slate-705 transition-all"
                    >
                      {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {isCopied ? "Скопировано!" : "Копировать"}
                    </button>
                  </div>

                  {/* CODE STREAM */}
                  <pre className="p-4 bg-slate-950 overflow-x-auto text-[11px] sm:text-xs text-slate-300 font-mono h-[450px] leading-relaxed relative scrollbar-thin">
                    <code>
                      {filesContent[selectedFile]}
                    </code>
                  </pre>

                </div>
              </div>

            </motion.div>
          )}

        </AnimatePresence>

        {/* METADATA INFO FOOTER */}
        <footer className="mt-16 border-t border-slate-900 pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <div>
            Built with Google AI Studio • AdomBot Beta Developer Dashboard
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono text-[10px]">Time: 2026-06-21 (UTC-7)</span>
            <span className="font-mono text-[10px]">Database Status: Mocked</span>
          </div>
        </footer>

      </div>
    </div>
  );
}
