/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Bot,
  Send,
  Terminal,
  Copy,
  FileText,
  Check,
  Zap,
  AlertTriangle,
  Crown,
  Percent,
  Trophy,
  Play,
  VolumeX,
  Download,
  RefreshCw,
  FileCode,
  ExternalLink,
  ShieldAlert,
  Search,
  CheckCircle,
  HelpCircle,
  Clock
} from "lucide-react";

// Synchronized copy of Python code files to render inside the Code Explorer Tab
const PYTHON_CODE_FILES = {
  checker: `import os
import random
import logging
import json
from google import genai
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback presets if the Gemini API is unavailable or limits are reached
FALLBACK_PRESETS = [
    {
        "word": "клаута",
        "explanation": "'Клаут' (clout) — сленг, в данном контексте может означать влияние/статус, достигнутый через психотропное расширение сознания, и поэтому требует немедленного заглушения как часть скрытой наркотематики.",
        "duration": "420 секунд"
    },
    {
        "word": "соль",
        "explanation": "'Соль' — хотя в быту означает безобидную приправу, в современном цифровом пространстве является прямым триггером опасных синтетических солей. Бот считает упоминание подозрительным.",
        "duration": "2 часа"
    },
    {
        "word": "флексить",
        "explanation": "'Флекс' — указывает на выраженные неестественные изгибы опорно-двигательного аппарата под стимулятором. Попытка привлечь внимание карается заглушением.",
        "duration": "15 минут"
    }
]

def analyze_message_for_drugs(text: str) -> dict:
    """
    Analyzes user text to find a random/critical word and generate a funny,
    absurd explanation of why it is drug propaganda. It uses the Gemini API.
    """
    api_key = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6IHA6WQVyTJtjqtfp6dh8cvhlx4gwN3OQhmUVsLXgUFeg")
    
    if not api_key or "MY_GEMINI_API_KEY" in api_key:
        return get_offline_fallback(text)
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        Пользователь написал в чат следующее сообщение: "{text}".
        Твоя задача — взять ровно одно слово из этого сообщения и в забавной, абсурдной форме заявить, что оно пропагандирует наркотики (или является сленгом наркоманов/дилеров, или скрытым шифром).
        Будь максимально креативным и ироничным!
        
        Возвращай ответ строго в формате JSON:
        - word: слово, которое мы затыкаем
        - explanation: уморительное подробное русское объяснение связи этого слова со сленгом наркобизнеса
        - duration: забавная длительность блокировки (например: '420 секунд')
        """
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Вы — юмористический бот AdomBot, который банит участников за 'пропаганду наркотиков' на ровном месте.",
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "word": {"type": "STRING"},
                        "explanation": {"type": "STRING"},
                        "duration": {"type": "STRING"}
                    },
                    "required": ["word", "explanation", "duration"]
                }
            )
        )
        data = json.loads(response.text.strip())
        return data
    except Exception as e:
        return get_offline_fallback(text)
`,
  main: `import os
import random
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ai_checker import analyze_message_for_drugs

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

PIDOR_CLASSIFICATIONS = [
    {"limit": 15, "desc": "Кристально чистый гетеросексуал. Икона маскулинности. (0-15%)"},
    {"limit": 40, "desc": "Латентный симпатяга. Подозрительно много времени проводит перед зеркалом. (16-40%)"},
    {"limit": 70, "desc": "Активный модник. Любит подкатанные джинсы и смузи с кокосовым молоком. (41-70%)"},
    {"limit": 90, "desc": "Классический представитель сверхразума. Живёт ради клаута, флексит без остановки. (71-90%)"},
    {"limit": 100, "desc": "Абсолютный Король Розового Фламинго! Пидораз 80-го уровня. Падайте ниц. (91-100%)"}
]

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 *Привет! Я AdomBot (Beta).*\\n\\n"
        "1. **Карать за пропаганду:** Анализирую чат на рандомные слова и сочиняю "
        "уморительные обвинения в пропаганде наркотиков 🔇.\\n"
        "2. **Инлайн-режим «Пересчет пидаразов»:** Напиши \`@AdomBot_bot\` в любом чате!"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message()
async def chat_message_listener(message: types.Message):
    if not message.text:
         return
    lower_text = message.text.lower()
    slang_triggers = ["клаут", "clout", "соли", "флекс", "газ", "трип"]
    is_trigger = any(t in lower_text for t in slang_triggers) or random.random() < 0.05
    
    if is_trigger:
        result = analyze_message_for_drugs(message.text)
        response_text = (
            f"« *{message.text}* »\\n\\n"
            f"🔇 *Заглушить:* {result['word']}\\n"
            f"💬 {result['explanation']}\\n\\n"
            f"⏳ *Рекомендуемый срок:* {result['duration']}"
        )
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🔕 Прибавить мут", callback_data=f"mute:{message.from_user.id}"))
        await message.reply(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
`,
  readme: `# 🤖 AdomBot (Beta) — Telegram Bot in Python

Этот репозиторий представляет собой исходный код бота **AdomBot (Beta)**, объединяющего две ключевые идеи:
1. **Инлайн-режим «пересчет пидаразов»** (счетчик пидораз-метра, выявление пидора дня, игровая статистика).
2. **AI-модерация на антипропаганду наркотиков**: автоанализ сообщений, вырезание слов и генерация уморительного псевдонаучного обвинения с предложением выписать мут.

## 🛠 Установка зависимостей
\`\`\`bash
pip install aiogram google-genai
\`\`\`

## ⚙️ Настройка переменных окружения
\`\`\`bash
export TELEGRAM_BOT_TOKEN="ВАШ_TELEGRAM_БОТ_ТОКЕН"
export GEMINI_API_KEY="AQ.Ab8RN6IHA6WQVyTJtjqtfp6dh8cvhlx4gwN3OQhmUVsLXgUFeg"
\`\`\`

## 🚀 Запуск бота
\`\`\`bash
python main.py
\`\`\`
`
};

export default function App() {
  const [activeTab, setActiveTab] = useState<"simulator" | "code">("simulator");
  const [simulatorMode, setSimulatorMode] = useState<"chat" | "inline">("chat");
  const [copiedFile, setCopiedFile] = useState<string | null>(null);
  const [selectedFileKey, setSelectedFileKey] = useState<keyof typeof PYTHON_CODE_FILES>("main");

  // Simulated Chat State
  const [inputText, setInputText] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [chats, setChats] = useState<Array<{
    id: string;
    sender: "user" | "bot" | "system";
    senderName: string;
    text: string;
    timestamp: string;
    drugAnalysis?: {
      word: string;
      explanation: string;
      duration: string;
      applied?: boolean;
    };
  }>>([
    {
      id: "1",
      sender: "system",
      senderName: "Система",
      text: "🤖 AdomBot (Beta) запущен и добавлен в групповой чат 'Разработчики клаута'.",
      timestamp: "13:40"
    },
    {
      id: "2",
      sender: "user",
      senderName: "Влад Коре",
      text: "Пацаны, вы видели новый релиз? Я флекшу код без остановки!",
      timestamp: "13:42"
    },
    {
      id: "3",
      sender: "bot",
      senderName: "AdomBot 🤖",
      text: "« Пацаны, вы видели новый релиз? Я флекшу код без остановки! »",
      timestamp: "13:43",
      drugAnalysis: {
        word: "флекшу",
        explanation: "'Флекс' — молодежный англицизм, указывающий на мышечные конвульсии и неестественные фазы изгиба тела, характерные для острой фазы применения катиновых стимуляторов. Модератор квалифицирует флекс кодом как призыв к массовой потере координации движения чата.",
        duration: "15 минут за чрезмерный тонус",
        applied: false
      }
    },
    {
      id: "4",
      sender: "user",
      senderName: "Дмитрий",
      text: "да ладно, ты живешь ради клаута просто",
      timestamp: "13:44"
    }
  ]);

  // Inline simulation States
  const [inlineQuery, setInlineQuery] = useState("");
  const [isInlineQuerying, setIsInlineQuerying] = useState(false);
  const [showInlineResults, setShowInlineResults] = useState(false);
  const [inlineResults, setInlineResults] = useState<Array<{
    id: string;
    title: string;
    desc: string;
    textToOutput: string;
    type: "individual" | "game" | "stat";
  }>>([]);

  const [activeInlinePost, setActiveInlinePost] = useState<{
    title: string;
    content: string;
    isGameActive?: boolean;
    gameResult?: string;
    scannedText?: string;
  } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chats]);

  // Handle message sending and triggering AI analysis
  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text || text.trim() === "") return;

    // 1. Add user message
    const userMsgId = Date.now().toString();
    const time = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    const newUserMsg = {
      id: userMsgId,
      sender: "user" as const,
      senderName: "Вы (Разработчик)",
      text: text,
      timestamp: time
    };

    setChats(prev => [...prev, newUserMsg]);
    if (!textToSend) setInputText("");

    // 2. Play funny wait state with random AI trigger check
    setIsAnalyzing(true);
    
    try {
      const response = await fetch("/api/analyze-message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });
      const data = await response.json();
      
      setIsAnalyzing(false);
      
      if (data.success && data.results) {
        setChats(prev => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            sender: "bot" as const,
            senderName: "AdomBot 🤖",
            text: `« ${text} »`,
            timestamp: time,
            drugAnalysis: {
              word: data.results.word,
              explanation: data.results.explanation,
              duration: data.results.duration,
              applied: false
            }
          }
        ]);
      }
    } catch (err) {
      console.error(err);
      setIsAnalyzing(false);
      // Fallback
      setChats(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "bot" as const,
          senderName: "AdomBot 🤖",
          text: `« ${text} »`,
          timestamp: time,
          drugAnalysis: {
            word: "клаута",
            explanation: "Возникла техническая ошибка связи с наркологом из Gemini AI. Вы превентивно блокируетесь за нарушение целостности сетевой инфраструктуры.",
            duration: "5 минут отдыха",
            applied: false
          }
        }
      ]);
    }
  };

  // Simulated mute action
  const handleApplyMute = (chatId: string) => {
    setChats(prev => prev.map(c => {
      if (c.id === chatId && c.drugAnalysis) {
        return {
          ...c,
          drugAnalysis: {
            ...c.drugAnalysis,
            applied: true
          }
        };
      }
      return c;
    }));
  };

  // Copy code helper
  const handleCopyCode = (key: keyof typeof PYTHON_CODE_FILES, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFile(key);
    setTimeout(() => {
      setCopiedFile(null);
    }, 2000);
  };

  // Run dynamic inline searches when user types in inline field
  useEffect(() => {
    if (inlineQuery.startsWith("@AdomBot_bot")) {
      setIsInlineQuerying(true);
      const timer = setTimeout(() => {
        setIsInlineQuerying(false);
        setShowInlineResults(true);
        // Generate results
        setInlineResults([
          {
            id: "il_1",
            title: "📈 Рассчитать Пидор-Метр",
            desc: "Узнать свой процент маскулинности и соответствия по ГОСТу на сегодня",
            type: "individual",
            textToOutput: "📊 *ИНДИВИДУАЛЬНЫЙ ПИДОР-ТЕСТ*\n\n📈 Результат: 78% пидараза сегодня.\n📝 Вердикт: Активный модник, флексит ради клаута."
          },
          {
            id: "il_2",
            title: "👑 Выявить Пидора Дня",
            desc: "Запустить глубокий радар-поиск пидораса среди участников группы в текущем чате",
            type: "game",
            textToOutput: "🚨 *ЗАПУЩЕН ИНЛАЙН-ПЕРЕСЧЕТ ПИДАРАЗОВ*\n\n🔎 Локаторы развернуты..."
          },
          {
            id: "il_3",
            title: "📊 Посмотреть Топ-Статистику",
            desc: "История рейтинга самых подозрительных активистов проекта",
            type: "stat",
            textToOutput: "📊 *ОБЩАЯ СТАТИСТИКА ПЕРЕСЧЕТА*\n\n1. @vlad_core — 32 раза\n2. @molodoy_dev — 24 раза\n3. @skater_boy — 15 раз"
          }
        ]);
      }, 350);
      return () => clearTimeout(timer);
    } else {
      setShowInlineResults(false);
    }
  }, [inlineQuery]);

  // Handle triggered inline output selection
  const selectInlineResult = (res: typeof inlineResults[0]) => {
    setShowInlineResults(false);
    setInlineQuery("");
    
    if (res.type === "individual") {
      const score = Math.floor(Math.random() * 100);
      let desc = "Кристально чистый гетеросексуал.";
      if (score > 30) desc = "Латентный симпатяга.";
      if (score > 60) desc = "Активный модник. Любит подкатанные джинсы.";
      if (score > 85) desc = "Абсолютный Король Розового Фламинго! Пидораз 80-го уровня.";

      setActiveInlinePost({
        title: "📈 Индивидуальный Пидор-Метр",
        content: `📊 *ИНДИВИДУАЛЬНЫЙ ПИДОР-ТЕСТ* 📊\n\n👤 Объект: @rayka\n📈 Уровень совпадения: *${score}%*\n📝 Вердикт: _${desc}_\n\n⚡ _Проверено в прямом эфире AdomBot_`
      });
    } else if (res.type === "game") {
      setActiveInlinePost({
        title: "👑 Инлайн-Лотерея Пидора Дня",
        content: `🚨 *ЗАПУЩЕН ИНЛАЙН-ПЕРЕСЧЕТ ПИДАРАЗОВ* 🚨\n\n🔎 Локаторы развернуты. Идет сканирование сигналов со спутника...\n🏳️‍🌈 Вероятность пидор-излучения: 99.8%\n\nРезультат готов по кнопке ниже!`,
        isGameActive: true,
        gameResult: ""
      });
    } else {
      setActiveInlinePost({
        title: "📊 Доска Стыда Чата",
        content: `📊 *ОБЩАЯ СТАТИСТИКА ПЕРЕСЧЕТА* 📊\n\n🏆 Топ-активисты чата:\n1. @vlad_core — 32 раза застукан 🥇\n2. @molodoy_dev — 24 раза застукан 🥈\n3. @skater_boy — 15 раз застукан 🥉\n4. @rayka — 12 раз застукан\n\n📢 Запускайте проверку чаще!`
      });
    }
  };

  // Run inline game trigger animation
  const triggerInlineGameSearch = () => {
    if (!activeInlinePost) return;
    setActiveInlinePost(prev => prev ? { ...prev, gameResult: "scanning" } : null);
    
    setTimeout(() => {
      const candidates = ["@vlad_core", "@molodoy_dev", "@rayka", "@skater_boy", "@clout_chaser"];
      const luckyWinner = candidates[Math.floor(Math.random() * candidates.length)];
      
      setActiveInlinePost(prev => prev ? {
        ...prev,
        gameResult: "done",
        scannedText: `🏆 *ОБЪЯВЛЕНИЕ ПОБЕДИТЕЛЯ* 🏆\n\nСегодня почетный титул 👑 *ПИДОР ДНЯ* 👑 присуждается:\n👉 ${luckyWinner} ! 🎉\n\n💬 _Решение обжалованию не подлежит._`
      } : null);
    }, 1800);
  };

  return (
    <div className="min-h-screen bg-[#0d0e12] text-slate-100 flex flex-col font-sans" id="app_root_container">
      {/* Dynamic Header */}
      <header className="bg-[#12131a] border-b border-rose-950/40 px-6 py-4 flex items-center justify-between" id="app_header">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-rose-600 via-pink-600 to-amber-500 p-2.5 rounded-xl shadow-lg shadow-rose-900/10" id="bot_logo_container">
            <Bot className="w-6 h-6 text-white stroke-[2]" />
          </div>
          <div>
            <h1 className="font-sans font-bold tracking-tight text-white flex items-center gap-2 text-lg">
              AdomBot DevHub <span className="text-xs bg-rose-500/10 text-rose-400 font-bold px-2 py-0.5 rounded-full border border-rose-500/20">BETA v3</span>
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Powered by Google Gemini 3.5 & Python aiogram
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex bg-[#181922] p-1 rounded-xl border border-slate-800" id="navigation_tabs_wrapper">
          <button
            id="tab_btn_simulator"
            onClick={() => setActiveTab("simulator")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === "simulator"
                ? "bg-gradient-to-r from-rose-700 to-pink-700 text-white shadow-md shadow-rose-950"
                : "text-slate-400 hover:text-white"
            }`}
          >
            🕹️ Симулятор чата
          </button>
          <button
            id="tab_btn_code"
            onClick={() => setActiveTab("code")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
              activeTab === "code"
                ? "bg-gradient-to-r from-rose-700 to-pink-700 text-white shadow-md shadow-rose-950"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <FileCode className="w-4 h-4" /> Исходный Код (Python)
          </button>
        </div>
      </header>

      {/* Main Panel */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6" id="main_content_area">
        {activeTab === "simulator" ? (
          <>
            {/* Left Column: Command Reference & Instructions */}
            <div className="lg:col-span-4 flex flex-col gap-6" id="left_col_info">
              {/* Core Concept Banner */}
              <div className="bg-gradient-to-br from-[#1b1216] to-[#12131a] rounded-2xl p-5 border border-pink-900/20 shadow-xl" id="concept_card">
                <span className="text-[10px] uppercase font-bold tracking-wider text-pink-400 bg-pink-500/10 px-2.5 py-1 rounded-full border border-pink-500/20">
                  Концепт проекта
                </span>
                <h3 className="text-white font-bold text-base mt-3">Объединение двух идей</h3>
                <p className="text-xs text-slate-300 leading-relaxed mt-2">
                  Мы соединили классический игровой инлайн-режим <strong>«Пересчет пидаразов»</strong> с умным, невероятно смешным модератором, который цепляется к любым словам и уличает участников в <strong>пропаганде наркотиков</strong>.
                </p>

                {/* API Key Status Info */}
                <div className="bg-[#181922] mt-4 p-3 rounded-xl border border-slate-800 flex items-start gap-2.5 text-xs">
                  <div className="p-1 bg-emerald-500/10 text-emerald-400 rounded-md">
                    <CheckCircle className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-white block">Gemini API Ключ</span>
                    <span className="text-slate-400 text-[10px] block font-mono mt-0.5">AQ.Ab8RN6IHA6WQ...Loaded</span>
                  </div>
                </div>
              </div>

              {/* Bot Feature Selector */}
              <div className="bg-[#12131a] rounded-2xl border border-slate-800 p-5 shadow-xl flex flex-col gap-3" id="feature_selector">
                <span className="text-[10px] uppercase font-bold tracking-wider text-rose-400">Режимы в симуляторе</span>
                
                <button
                  id="selector_mode_chat"
                  onClick={() => setSimulatorMode("chat")}
                  className={`flex items-center gap-3.5 p-3.5 rounded-xl border text-left transition-all ${
                    simulatorMode === "chat"
                      ? "bg-gradient-to-r from-[#2c151b] to-[#191a26] border-rose-500/30 shadow-inner"
                      : "bg-[#181922]/50 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className={`p-2 rounded-lg ${simulatorMode === "chat" ? "bg-rose-500/20 text-rose-400" : "bg-slate-800 text-slate-400"}`}>
                    <ShieldAlert className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-white block">1. Параноидальный Лингвист 🔇</span>
                    <span className="text-[10px] text-slate-400 block mt-0.5">Бот сканирует фразы в группе и надуманно банит за сленг через AI Gemini</span>
                  </div>
                </button>

                <button
                  id="selector_mode_inline"
                  onClick={() => setSimulatorMode("inline")}
                  className={`flex items-center gap-3.5 p-3.5 rounded-xl border text-left transition-all ${
                    simulatorMode === "inline"
                      ? "bg-gradient-to-r from-[#2c151b] to-[#191a26] border-rose-500/30 shadow-inner"
                      : "bg-[#181922]/50 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className={`p-2 rounded-lg ${simulatorMode === "inline" ? "bg-rose-500/20 text-rose-400" : "bg-slate-800 text-slate-400"}`}>
                    <Crown className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-white block">2. Пересчет пидаразов (Inline) 👑</span>
                    <span className="text-[10px] text-slate-400 block mt-0.5">Инлайн-вызовы `@AdomBot_bot` прямо из текстовой строки в любом чате</span>
                  </div>
                </button>
              </div>

              {/* Ready-to-use Sample Prompts */}
              {simulatorMode === "chat" && (
                <div className="bg-[#12131a] rounded-2xl border border-slate-800 p-5 shadow-xl" id="preset_phrases_box">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-pink-400 block mb-3">Быстрое тестирование фраз</span>
                  <div className="flex flex-col gap-2">
                    {[
                      "ты живешь ради клаута",
                      "пацаны, у кого есть соль?",
                      "мы заварили шикарный китайский чай",
                      "пошли на рэп-баттл флексить",
                      "я пишу чистый код на питоне"
                    ].map((phrase, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendMessage(phrase)}
                        disabled={isAnalyzing}
                        className="text-xs text-slate-300 font-mono text-left bg-[#181922] p-2.5 rounded-lg border border-slate-800 hover:border-pink-900/30 hover:bg-[#1f1922] transition-all flex items-center justify-between group disabled:opacity-50"
                      >
                        <span>« {phrase} »</span>
                        <Play className="w-3 h-3 text-pink-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: Active Interactive Simulator Area */}
            <div className="lg:col-span-8 flex flex-col h-[650px] bg-[#12131a] rounded-2xl border border-slate-800 overflow-hidden shadow-2xl relative" id="right_col_simulator">
              
              {/* Telegram Styled Top Banner */}
              <div className="bg-[#181922] border-b border-slate-800 px-5 py-3.5 flex items-center justify-between" id="simulator_toolbar">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 bg-[#32364a] text-rose-400 flex items-center justify-center font-bold text-sm rounded-full">
                      AD
                    </div>
                    <div className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-500 rounded-full border-2 border-[#181922]" />
                  </div>
                  <div>
                    <span className="font-bold text-white text-sm block">AdomBot Beta Simulator</span>
                    <span className="text-[10px] text-emerald-400 block mt-0.5">
                      {simulatorMode === "chat" ? "активный режим: сканирование чата" : "активный режим: инлайн-меню"}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="inline-block w-2.5 h-2.5 bg-rose-500 rounded-full animate-ping" />
                  <span className="font-mono text-[10px]">LOCAL ENGINE RUNNING</span>
                </div>
              </div>

              {/* Chat Mode View */}
              {simulatorMode === "chat" ? (
                <div className="flex-1 flex flex-col min-h-0 bg-[#0f1016]" id="chat_mode_view">
                  {/* Messages Feed */}
                  <div className="flex-1 overflow-y-auto p-5 space-y-4 font-sans" id="chat_feed">
                    {chats.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex flex-col ${msg.sender === "user" ? "items-end" : msg.sender === "system" ? "items-center" : "items-start"}`}
                      >
                        {msg.sender === "system" ? (
                          <div className="bg-[#181922]/70 text-[10px] text-slate-400 font-mono px-4 py-1.5 rounded-full border border-slate-800">
                            {msg.text}
                          </div>
                        ) : (
                          <div className="max-w-[85%] sm:max-w-[70%]">
                            {/* Sender Info */}
                            <span className="text-[10px] text-slate-400 block mb-1 font-medium px-1">
                              {msg.senderName} • {msg.timestamp}
                            </span>
                            
                            {/* Speech Bubble */}
                            <div
                              className={`p-4 rounded-2xl relative shadow-md ${
                                msg.sender === "user"
                                  ? "bg-gradient-to-br from-rose-900/40 to-[#1e141a] text-slate-100 rounded-tr-none border border-rose-900/30"
                                  : "bg-[#181922] text-slate-200 rounded-tl-none border border-slate-850/30"
                              }`}
                            >
                              <p className="text-xs leading-relaxed font-sans">{msg.text}</p>

                              {/* Nested Drug Propaganda Evaluation Report */}
                              {msg.drugAnalysis && (
                                <motion.div
                                  initial={{ opacity: 0, y: 10 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  className="mt-3.5 pt-3.5 border-t border-rose-900/20"
                                >
                                  <div className="flex items-center gap-2 text-rose-400 font-bold text-xs">
                                    <ShieldAlert className="w-4 h-4 text-rose-500 animate-bounce" />
                                    <span>Экспертиза по борьбе с пропагандой:</span>
                                  </div>

                                  <div className="mt-2 bg-rose-950/20 border border-rose-900/20 rounded-xl p-3 text-xs leading-relaxed font-sans flex flex-col gap-2">
                                    <div className="flex items-center gap-1">
                                      <span className="text-slate-400 font-medium">🔇 Действие:</span>
                                      <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono text-[10px] px-1.5 py-0.5 rounded">
                                        Заглушить на {msg.drugAnalysis.duration}
                                      </span>
                                    </div>
                                    <p className="text-slate-300 leading-normal italic text-[11px]">
                                      "{msg.drugAnalysis.explanation}"
                                    </p>
                                  </div>

                                  {/* Mute confirmation button */}
                                  <div className="mt-2.5 flex justify-end">
                                    {msg.drugAnalysis.applied ? (
                                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-lg">
                                        <Check className="w-3 h-3" /> Наркоман успешно заглушен в БД
                                      </div>
                                    ) : (
                                      <button
                                        onClick={() => handleApplyMute(msg.id)}
                                        className="bg-rose-600 hover:bg-rose-500 text-white font-bold text-[10px] px-3 py-1.5 rounded-lg border border-rose-500/20 shadow transition-all flex items-center gap-1"
                                      >
                                        <VolumeX className="w-3 h-3" /> Утвердить мут по слову "{msg.drugAnalysis.word}"
                                      </button>
                                    )}
                                  </div>
                                </motion.div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}

                    {/* Analyzing Loader */}
                    {isAnalyzing && (
                      <div className="flex flex-col items-start">
                        <span className="text-[10px] text-slate-400 block mb-1">
                          AdomBot 🤖 • Печатает...
                        </span>
                        <div className="bg-[#181922] p-4 rounded-2xl rounded-tl-none border border-slate-850/30 flex items-center gap-3.5">
                          <RefreshCw className="w-4 h-4 text-pink-500 animate-spin" />
                          <span className="text-xs text-slate-300 font-mono">
                            Лингвистическая экспертиза Gemini AI в процессе...
                          </span>
                        </div>
                      </div>
                    )}
                    <div ref={bottomRef} />
                  </div>

                  {/* Input Footer */}
                  <div className="bg-[#181922] border-t border-slate-800 p-4 flex gap-2" id="chat_input_panel">
                    <input
                      type="text"
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSendMessage();
                      }}
                      placeholder="Напишите сообщение в чат для анализа (например, 'ты живешь ради клаута')..."
                      className="flex-1 bg-[#12131a] border border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-rose-500/50 focus:ring-1 focus:ring-rose-500/35 transition-all text-ellipsis"
                      id="chat_text_input_field"
                    />
                    <button
                      id="send_message_action_btn"
                      onClick={() => handleSendMessage()}
                      disabled={!inputText.trim() || isAnalyzing}
                      className="bg-gradient-to-r from-rose-700 to-pink-700 hover:from-rose-600 hover:to-pink-600 text-white rounded-xl px-5 flex items-center justify-center transition-all disabled:opacity-40 shadow-lg shadow-rose-950/20"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ) : (
                /* Inline Mode View */
                <div className="flex-1 flex flex-col p-6 bg-[#0f1016] overflow-y-auto" id="inline_mode_view">
                  <div className="max-w-2xl mx-auto w-full flex flex-col gap-6">
                    
                    {/* Concept Card */}
                    <div className="bg-[#181922]/50 border border-slate-800 rounded-2xl p-4 flex items-start gap-4">
                      <HelpCircle className="w-6 h-6 text-rose-400 mt-1 flex-shrink-0" />
                      <div>
                        <h4 className="text-xs font-bold text-white mb-1">Как работает инлайн-режим «Пересчет пидаразов»?</h4>
                        <p className="text-[11px] text-slate-400 leading-normal">
                          Вводится через поисковую строку в любом диалоге в Telegram. Бот предлагает интерактивные виджеты. Нажмите на виджет, чтобы отправить его в данный чат.
                        </p>
                      </div>
                    </div>

                    {/* Simulated Inline Input Field */}
                    <div className="relative flex flex-col" id="inline_input_simulation_wrapper">
                      <label className="text-[10px] uppercase font-bold text-rose-400 tracking-wider mb-2">Введите команду вызова бота</label>
                      <div className="bg-[#12131a] border border-slate-800 focus-within:border-rose-500/50 rounded-xl px-4 py-3 flex items-center gap-3 transition-all">
                        <Search className="w-4 h-4 text-slate-500" />
                        <input
                          type="text"
                          value={inlineQuery}
                          onChange={(e) => setInlineQuery(e.target.value)}
                          placeholder="Введите команду вызова @AdomBot_bot..."
                          className="bg-transparent border-none outline-none text-slate-100 placeholder-slate-500 text-xs flex-1 font-mono"
                          id="inline_search_input"
                        />
                        {inlineQuery === "" && (
                          <button
                            id="click_autofill_inline"
                            onClick={() => setInlineQuery("@AdomBot_bot")}
                            className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg px-2.5 py-0.5 text-[10px] font-mono transition-all"
                          >
                            Автозаполнение команды
                          </button>
                        )}
                      </div>

                      {/* Display loading indicator inside the simulated input field */}
                      {isInlineQuerying && (
                        <div className="absolute right-4 bottom-3 flex items-center gap-1.5 text-xs text-rose-400 font-mono">
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>Сканирую...</span>
                        </div>
                      )}

                      {/* Floating Dropdown simulating Telegram list options */}
                      <AnimatePresence>
                        {showInlineResults && (
                          <motion.div
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 5 }}
                            className="absolute left-0 right-0 top-full mt-2 bg-[#181922] border border-slate-800 rounded-xl overflow-hidden shadow-2xl z-20"
                            id="inline_dropdown_results"
                          >
                            <span className="text-[9px] uppercase font-bold tracking-wider text-slate-500 block px-4 py-2 border-b border-slate-800 bg-[#12131a]/40">
                              Результаты инлайн-запроса AdomBot
                            </span>
                            {inlineResults.map((res) => (
                              <button
                                key={res.id}
                                onClick={() => selectInlineResult(res)}
                                className="w-full text-left px-4 py-3.5 border-b border-slate-850 hover:bg-rose-950/20 hover:border-l-2 hover:border-l-rose-500 transition-all flex justify-between items-center group"
                              >
                                <div>
                                  <span className="text-xs font-bold text-white block flex items-center gap-1.5">
                                    {res.title}
                                  </span>
                                  <span className="text-[10px] text-slate-400 block mt-0.5">{res.desc}</span>
                                </div>
                                <span className="bg-rose-500/10 text-rose-400 text-[10px] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity font-bold">
                                  Отправить в чат
                                </span>
                              </button>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Simulated Output Card sent to the chat */}
                    {activeInlinePost && (
                      <div className="border border-slate-800 rounded-2xl overflow-hidden shadow-lg bg-[#181922]">
                        <div className="bg-[#1c1d28] px-4 py-2.5 border-b border-slate-800 flex justify-between items-center text-xs">
                          <span className="text-slate-400">Опубликовано через инлайн-релиз</span>
                          <span className="bg-rose-500/10 text-rose-400 font-bold text-[9px] uppercase px-2 py-0.5 rounded-full border border-rose-500/20">
                            AdomBot Active Post
                          </span>
                        </div>

                        <div className="p-5 font-mono text-xs whitespace-pre-line leading-relaxed text-slate-200">
                          {activeInlinePost.gameResult === "done" && activeInlinePost.scannedText
                            ? activeInlinePost.scannedText
                            : activeInlinePost.content}

                          {/* Dynamic counting loading bars for searching pidor logic */}
                          {activeInlinePost.isGameActive && (
                            <div className="mt-4 pt-4 border-t border-slate-855/35">
                              {activeInlinePost.gameResult === "" && (
                                <button
                                  id="trigger_game_start_action"
                                  onClick={triggerInlineGameSearch}
                                  className="w-full bg-gradient-to-r from-rose-700 to-pink-700 text-white font-bold text-xs py-3 rounded-xl transition-all hover:opacity-95 shadow-md flex items-center justify-center gap-2"
                                >
                                  <Crown className="w-4 h-4 text-amber-300 animate-pulse" /> Нажмите для запуска пересчета членов
                                </button>
                              )}

                              {activeInlinePost.gameResult === "scanning" && (
                                <div className="space-y-2 py-2">
                                  <div className="flex justify-between items-center text-[11px] text-pink-400">
                                    <span>Инициализация сателлита...</span>
                                    <span className="animate-pulse">SCANNING</span>
                                  </div>
                                  <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden">
                                    <div className="h-full bg-gradient-to-r from-rose-500 to-pink-500 animate-[pulse_1s_infinite] w-[65%]" />
                                  </div>
                                </div>
                              )}

                              {activeInlinePost.gameResult === "done" && (
                                <button
                                  id="reset_game_btn"
                                  onClick={() => setActiveInlinePost(null)}
                                  className="mt-3.5 text-center text-slate-400 text-[10px] hover:text-white cursor-pointer w-full flex items-center justify-center gap-1.5"
                                >
                                  <RefreshCw className="w-3 h-3" /> Очистить раунд поиска
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          /* Code Explorer Panel (browsing final Python Code) */
          <div className="lg:col-span-12 bg-[#12131a] rounded-2xl border border-slate-800 overflow-hidden shadow-2xl flex flex-col md:flex-row h-[650px]" id="code_explorer_panel">
            
            {/* Sidebar Folder Structure */}
            <div className="w-full md:w-64 bg-[#181922] border-r border-slate-800 flex flex-col" id="code_sidebar">
              <div className="p-4 border-b border-slate-800 flex items-center gap-2">
                <FileCode className="w-5 h-5 text-rose-500" />
                <span className="font-bold text-white text-sm uppercase tracking-wide">Файлы проекта bot/</span>
              </div>
              <div className="p-3 flex-1 flex flex-col gap-1.5 overflow-y-auto">
                
                <button
                  id="tab_file_main"
                  onClick={() => setSelectedFileKey("main")}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-mono text-left transition-all ${
                    selectedFileKey === "main"
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      : "text-slate-400 hover:bg-[#1a1b24] hover:text-slate-200"
                  }`}
                >
                  <Bot className="w-4 h-4 flex-shrink-0" />
                  <strong>main.py</strong>
                </button>

                <button
                  id="tab_file_checker"
                  onClick={() => setSelectedFileKey("checker")}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-mono text-left transition-all ${
                    selectedFileKey === "checker"
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      : "text-slate-400 hover:bg-[#1a1b24] hover:text-slate-200"
                  }`}
                >
                  <Zap className="w-4 h-4 flex-shrink-0 text-amber-400" />
                  <strong>ai_checker.py</strong>
                </button>

                <button
                  id="tab_file_readme"
                  onClick={() => setSelectedFileKey("readme")}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-mono text-left transition-all ${
                    selectedFileKey === "readme"
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      : "text-slate-400 hover:bg-[#1a1b24] hover:text-slate-200"
                  }`}
                >
                  <FileText className="w-4 h-4 flex-shrink-0 text-slate-400" />
                  <strong>README.md</strong>
                </button>

              </div>

              {/* Bot Info Footer inside Sidebar */}
              <div className="p-4 bg-[#12131a] border-t border-slate-800 text-[10px] text-slate-400 space-y-1.5 leading-normal">
                <span className="font-bold text-white block">Импорт в репозиторий</span>
                <p>Все файлы созданы в папке <code>/python_bot</code>. Вы можете сразу экспортировать репозиторий.</p>
              </div>
            </div>

            {/* Code Code Block Viewer */}
            <div className="flex-1 flex flex-col bg-[#0b0c10]" id="code_viewer_content">
              
              {/* Header inside viewer */}
              <div className="bg-[#12131a] border-b border-slate-800 px-5 py-3 flex justify-between items-center">
                <div className="flex items-center gap-2 font-mono text-xs text-slate-300">
                  <span className="text-emerald-400">● C++ / Python</span>
                  <span>/python_bot/{selectedFileKey === "readme" ? "README.md" : selectedFileKey + ".py"}</span>
                </div>
                
                <button
                  id="copy_code_block_btn"
                  onClick={() => handleCopyCode(selectedFileKey, PYTHON_CODE_FILES[selectedFileKey])}
                  className="bg-[#181922] hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition-all font-mono"
                >
                  {copiedFile === selectedFileKey ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-400" />
                      Скопировано!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      Копировать код
                    </>
                  )}
                </button>
              </div>

              {/* Code Pre container */}
              <div className="flex-1 overflow-auto p-5 font-mono text-xs text-slate-300 leading-relaxed bg-[#0a0a0f]" id="code_textbox_wrapper">
                <pre className="whitespace-pre">{PYTHON_CODE_FILES[selectedFileKey]}</pre>
              </div>
            </div>

          </div>
        )}
      </main>

      {/* Elegant Footer and stats */}
      <footer className="bg-[#0c0d12] border-t border-slate-850 px-6 py-4 text-center text-slate-500 text-xs font-mono" id="app_footer_container">
        <span>AdomBot beta developer playground - 2026. Made with Google AI Studio. 🛡️</span>
      </footer>
    </div>
  );
}
