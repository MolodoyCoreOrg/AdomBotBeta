import { useState, FormEvent } from "react";
import { 
  Bot, 
  CheckCircle2, 
  Clipboard, 
  ExternalLink, 
  Lock, 
  Users, 
  Check, 
  BookOpen, 
  Terminal,
  MessageSquare,
  ShieldAlert,
  ArrowRight
} from "lucide-react";

interface MockSlot {
  number: number;
  username?: string;
  firstName?: string;
  isOccupied: boolean;
  registeredAt?: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"telegraf" | "grammy" | "node-telegram">("telegraf");
  const [copied, setCopied] = useState(false);
  const [slots, setSlots] = useState<MockSlot[]>(() => {
    const list: MockSlot[] = [];
    for (let i = 1; i <= 100; i++) {
      // Seed a few fun mock ones to make it look alive
      if (i === 7) {
        list.push({ number: i, username: "flameasfuck", firstName: "Админ Flame", isOccupied: true, registeredAt: "2026-06-21T02:11:00Z" });
      } else if (i === 24) {
        list.push({ number: i, username: "molodoy_core", firstName: "Molodoy", isOccupied: true, registeredAt: "2026-06-21T03:45:00Z" });
      } else if (i === 69) {
        list.push({ number: i, username: "sladkiy_malchik", firstName: "Сладенький", isOccupied: true, registeredAt: "2026-06-21T05:00:00Z" });
      } else {
        list.push({ number: i, isOccupied: false });
      }
    }
    return list;
  });

  const [selectedSlot, setSelectedSlot] = useState<MockSlot | null>(slots[6]); // default Pidaraz 7
  const [newSlotNum, setNewSlotNum] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newFirstName, setNewFirstName] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSimulateRegister = (e: FormEvent) => {
    e.preventDefault();
    const num = parseInt(newSlotNum, 10);
    if (isNaN(num) || num < 1 || num > 100) {
      setStatusMessage("❌ Введите корректный номер от 1 до 100!");
      return;
    }

    if (!newFirstName.trim()) {
      setStatusMessage("❌ Напишите ваше имя!");
      return;
    }

    const existing = slots.find(s => s.number === num);
    if (existing?.isOccupied) {
      setStatusMessage(`❌ Номер ${num} уже занят! Выберите другой.`);
      return;
    }

    // Assign slot
    const updated = slots.map(s => {
      if (s.number === num) {
        return {
          number: num,
          username: newUsername.trim() || undefined,
          firstName: newFirstName,
          isOccupied: true,
          registeredAt: new Date().toISOString()
        };
      }
      return s;
    });

    setSlots(updated);
    const assigned = updated.find(s => s.number === num)!;
    setSelectedSlot(assigned);
    setStatusMessage(`🎉 Вы успешно заняли слот Пидараз ${num}!`);
    setNewSlotNum("");
    setNewUsername("");
    setNewFirstName("");
  };

  // Code snippets for visual display
  const telegrafCode = `// src/bot/telegraf-bot.ts
import { Telegraf, Markup } from 'telegraf';
import { JsonFileStorage } from './storage';

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN!);
const storage = new JsonFileStorage();

// Number selection via plain text
bot.on('text', async (ctx) => {
  const num = parseInt(ctx.message.text.trim(), 10);
  if (isNaN(num) || num < 1 || num > 100) return;

  const res = await storage.chooseSlot(
    ctx.from.id,
    ctx.from.username,
    ctx.from.first_name,
    ctx.from.last_name,
    num
  );

  if (res.success) {
    ctx.reply(\`🎉 Вы успешно зарезервировали слот Пидараз \${num}!\`);
  } else {
    ctx.reply(\`❌ Ошибка: \${res.error}\`);
  }
});

// Inline query mode
bot.on('inline_query', async (ctx) => {
  const user = await storage.getUser(ctx.from.id);
  if (user && user.slotNumber) {
    ctx.answerInlineQuery([
      {
        type: 'article',
        id: \`pidaraz_\${user.slotNumber}\`,
        title: 'Пересчет Пидаразов',
        description: \`Отправить: "Пидараз \${user.slotNumber} на связи"\`,
        input_message_content: {
          message_text: \`🏳️‍🌈 Пидараз \${user.slotNumber} (@\${user.username || ctx.from.first_name}) на связи!\`,
          parse_mode: 'Markdown'
        }
      }
    ]);
  } else {
    ctx.answerInlineQuery([
      {
        type: 'article',
        id: 'no_number',
        title: 'Я безномерный пидараз 🤷‍♂️',
        description: 'Нажми, чтобы зайти в бота и выбрать номер',
        input_message_content: {
          message_text: 'Я безномерный пидараз... 🤷‍♂️'
        },
        reply_markup: {
          inline_keyboard: [[{ text: 'Выбрать номер 🏳️‍🌈', url: 'https://t.me/your_bot?start=choose' }]]
        }
      }
    ]);
  }
});`;

  const grammyCode = `// src/bot/grammy-bot.ts
import { Bot, InlineKeyboard } from 'grammy';
import { JsonFileStorage } from './storage';

const bot = new Bot(process.env.TELEGRAM_BOT_TOKEN!);
const storage = new JsonFileStorage();

// Handle plain message numbers (1-100)
bot.on('message:text', async (ctx) => {
  const num = parseInt(ctx.message.text.trim(), 10);
  if (isNaN(num) || num < 1 || num > 100) return;

  const res = await storage.chooseSlot(
    ctx.from.id,
    ctx.from.username,
    ctx.from.first_name,
    ctx.from.last_name,
    num
  );

  if (res.success) {
    ctx.reply(\`🎉 Успешно зарезервирован слот Пидараз \${num}!\`);
  } else {
    ctx.reply(\`❌ Ошибка: \${res.error}\`);
  }
});

// Inline query handler
bot.on('inline_query', async (ctx) => {
  const user = await storage.getUser(ctx.from.id);
  if (user && user.slotNumber) {
    ctx.answerInlineQuery([
      {
        type: 'article',
        id: \`pidaraz_\${user.slotNumber}\`,
        title: 'Пересчет Пидаразов',
        description: \`Отправить: "Пидараз \${user.slotNumber} на связи"\`,
        input_message_content: {
          message_text: \`🏳️‍🌈 Пидараз \${user.slotNumber} на связи!\`
        }
      }
    ]);
  } else {
    ctx.answerInlineQuery([
      {
        type: 'article',
        id: 'no_num',
        title: 'Я безномерный пидараз 🤷‍♂️',
        input_message_content: { message_text: 'Я безномерный пидараз...' },
        reply_markup: new InlineKeyboard().url('Выбрать номер 🏳️‍🌈', 'https://t.me/your_bot?start=choose')
      }
    ]);
  }
});`;

  const nodeTelegramCode = `// src/bot/node-telegram-bot-api.ts
import TelegramBot from 'node-telegram-bot-api';
import { JsonFileStorage } from './storage';

const bot = new TelegramBot(process.env.TELEGRAM_BOT_TOKEN!, { polling: true });
const storage = new JsonFileStorage();

bot.on('message', async (msg) => {
  if (!msg.text || msg.text.startsWith('/')) return;
  const num = parseInt(msg.text.trim(), 10);
  if (isNaN(num) || num < 1 || num > 100) return;

  const res = await storage.chooseSlot(
    msg.from!.id,
    msg.from!.username,
    msg.from!.first_name,
    msg.from!.last_name,
    num
  );

  if (res.success) {
    bot.sendMessage(msg.chat.id, \`🎉 Успешно выбран слот Пидараз \${num}!\`);
  } else {
    bot.sendMessage(msg.chat.id, \`❌ Ошибка: \${res.error}\`);
  }
});`;

  const getCodeStr = () => {
    switch(activeTab) {
      case "telegraf": return telegrafCode;
      case "grammy": return grammyCode;
      case "node-telegram": return nodeTelegramCode;
    }
  };

  const occupiedCount = slots.filter(s => s.isOccupied).length;

  return (
    <div className="min-h-screen bg-[#0d0e12] text-[#f1f3f9] font-sans selection:bg-purple-600 selection:text-white" id="container_root">
      {/* Decorative gradient header banner */}
      <div className="h-2 bg-gradient-to-r from-red-500 via-orange-500 via-yellow-400 via-green-500 via-blue-500 to-purple-600" id="header_decor"></div>

      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8" id="app_content">
        
        {/* Title Block */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-gray-800 pb-8 mb-8" id="title_block">
          <div>
            <div className="flex items-center gap-3 mb-2" id="badge_group">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-900/40 text-purple-300 border border-purple-800/60" id="badge_status">
                <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse"></span>
                Telegram Bot Modules
              </span>
              <span className="text-xs text-gray-500 uppercase tracking-widest font-mono" id="recount_ver">v1.0.0</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white flex items-center gap-2.5" id="main_title">
              🏳️‍🌈 Пересчет Пидаразов <span className="text-xs sm:text-sm font-normal text-purple-400 font-mono px-2 py-1 bg-purple-950/50 rounded border border-purple-900/30">dev branch</span>
            </h1>
            <p className="mt-2 text-sm sm:text-base text-gray-400 max-w-2xl" id="main_description">
              Универсальные модули для расширения функционала вашего бота. Реализован уникальный пожизненный выбор номеров (1-100), утренний пересчет со сбором отметок и поддержка инлайн-режима во всех чатах.
            </p>
          </div>
          
          <div className="mt-4 md:mt-0 flex flex-wrap gap-2.5" id="action_buttons">
            <a 
              href="https://github.com/MolodoyCoreOrg/AdomBotBeta/tree/dev" 
              target="_blank" 
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 active:bg-gray-900 text-sm font-medium rounded-lg text-white border border-gray-700 transition"
              id="btn_repo"
            >
              <Terminal className="h-4 w-4 text-purple-400" />
              <span>Репозиторий проекта</span>
              <ExternalLink className="h-3 w-3 text-gray-500" />
            </a>
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8" id="info_grid">
          
          {/* Card 1: Bot Concept */}
          <div className="p-6 bg-[#13151c] rounded-xl border border-gray-800/80 hover:border-gray-700/60 transition" id="concept_card">
            <div className="h-10 w-10 rounded-lg bg-orange-950/50 border border-orange-500/20 flex items-center justify-center mb-4" id="c1_icon">
              <Bot className="h-5 w-5 text-orange-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2" id="c1_title">1. Выбор Номера (1-100)</h3>
            <p className="text-sm text-gray-400 leading-relaxed" id="c1_desc">
              Человек отправляет боту любое число в ЛС. Бот проверяет свободность слота и жестко закрепляет его за пользователем навсегда. Изменить выбор нельзя. База имеет лимит в 100 слотов (легко настраивается).
            </p>
          </div>

          {/* Card 2: Interactive Inline */}
          <div className="p-6 bg-[#13151c] rounded-xl border border-gray-800/80 hover:border-gray-700/60 transition" id="inline_card">
            <div className="h-10 w-10 rounded-lg bg-purple-950/50 border border-purple-500/20 flex items-center justify-center mb-4" id="c2_icon">
              <MessageSquare className="h-5 w-5 text-purple-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2" id="c2_title">2. Инлайн-вызов через @</h3>
            <p className="text-sm text-gray-400 leading-relaxed" id="c2_desc">
              В любом чате впишите юзернейм бота (например, <code className="text-purple-300 font-mono">@CuCbKu_gg_bot</code>). Если номер выбран, бот предложит отправить "Пидараз N на связи". Если номера нет, выдаст кнопку "Выбрать номер" со ссылкой на ЛС.
            </p>
          </div>

          {/* Card 3: Morning Recount */}
          <div className="p-6 bg-[#13151c] rounded-xl border border-gray-800/80 hover:border-gray-700/60 transition" id="morning_card">
            <div className="h-10 w-10 rounded-lg bg-green-950/50 border border-green-500/20 flex items-center justify-center mb-4" id="c3_icon">
              <Users className="h-5 w-5 text-green-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2" id="c3_title">3. Утренний Пересчет</h3>
            <p className="text-sm text-gray-400 leading-relaxed" id="c3_desc">
              Автоматическая утренняя рассылка в ЛС всем участникам с запросом "Пидараз N на связи???". При нажатии на кнопку бот делает глобальный анонс по всей базе: "Пидараз N на связи!", фиксируя явку на сегодня.
            </p>
          </div>

        </div>

        {/* Dashboard Panels */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8" id="dashboard_panels">
          
          {/* LEFT: Live Interactive Registry Visualizer */}
          <div className="xl:col-span-7 bg-[#13151c] rounded-xl border border-gray-800 p-6" id="visualizer_panel">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-4 mb-6" id="viz_header">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2" id="viz_title">
                  🔍 Интерактивный Стенд (Реестр 100 Слотов)
                </h2>
                <p className="text-xs text-gray-400 mt-1" id="viz_subtitle">
                  Здесь вы можете занять любой свободный номер для предпросмотра структуры данных
                </p>
              </div>
              <div className="bg-gray-900 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center gap-2 text-xs text-gray-300 font-mono" id="viz_counter">
                <span>Занято слотов:</span>
                <span className="font-bold text-purple-400">{occupiedCount} / 100</span>
              </div>
            </div>

            {/* Quick Simulation Form */}
            <form onSubmit={handleSimulateRegister} className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-[#181a24] p-4 rounded-xl border border-gray-800 mb-6" id="sim_form">
              <div className="flex flex-col" id="col_num">
                <label className="text-[10px] uppercase font-mono tracking-wider text-gray-400 mb-1">Номер (1-100)</label>
                <input 
                  type="number" 
                  min="1" 
                  max="100" 
                  required
                  placeholder="7, 42, 99..."
                  value={newSlotNum}
                  onChange={(e) => setNewSlotNum(e.target.value)}
                  className="bg-gray-900 border border-gray-700/80 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 font-mono"
                  id="input_num"
                />
              </div>
              <div className="flex flex-col sm:col-span-2" id="col_name">
                <label className="text-[10px] uppercase font-mono tracking-wider text-gray-400 mb-1">Имя в Telegram (First Name)</label>
                <input 
                  type="text" 
                  required
                  placeholder="Например, Александр"
                  value={newFirstName}
                  onChange={(e) => setNewFirstName(e.target.value)}
                  className="bg-gray-900 border border-gray-700/80 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500"
                  id="input_firstname"
                />
              </div>
              <div className="flex flex-col" id="col_submit">
                <label className="text-[10px] uppercase font-mono tracking-wider text-gray-400 mb-1">Действие</label>
                <button 
                  type="submit"
                  className="bg-purple-600 hover:bg-purple-500 active:bg-purple-700 text-white text-xs font-semibold rounded px-4 py-2 transition h-full flex items-center justify-center gap-1.5"
                  id="btn_sim_submit"
                >
                  Занять слот
                  <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              <div className="sm:col-span-4" id="col_username">
                <input 
                  type="text" 
                  placeholder="Юзернейм без @ (опционально)"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="bg-gray-900/60 border border-gray-800 rounded px-3 py-1 text-xs text-gray-300 w-full focus:outline-none focus:border-purple-500 font-mono"
                  id="input_username"
                />
              </div>
            </form>

            {statusMessage && (
              <div className={`p-2.5 rounded-lg text-xs font-medium mb-6 text-center border ${
                statusMessage.startsWith("❌") 
                  ? "bg-red-950/40 text-red-300 border-red-900/40" 
                  : "bg-green-950/40 text-green-300 border-green-900/40"
              }`} id="form_status">
                {statusMessage}
              </div>
            )}

            {/* Grid 1-100 */}
            <div className="grid grid-cols-5 sm:grid-cols-10 gap-2 mb-6 max-h-[300px] overflow-y-auto pr-1 border border-gray-800/80 p-3 rounded-lg bg-[#0e1015]" id="slots_grid">
              {slots.map((slot) => (
                <button
                  key={slot.number}
                  type="button"
                  onClick={() => setSelectedSlot(slot)}
                  className={`aspect-square rounded flex flex-col items-center justify-center border transition relative text-xs font-mono font-bold ${
                    slot.isOccupied 
                      ? selectedSlot?.number === slot.number
                        ? "bg-purple-600 border-purple-400 text-white shadow-lg shadow-purple-500/20"
                        : "bg-purple-950/50 border-purple-800 text-purple-300 hover:bg-purple-900/60"
                      : selectedSlot?.number === slot.number
                        ? "bg-gray-800 border-purple-500 text-purple-300"
                        : "bg-gray-905 border-gray-800 text-gray-500 hover:border-gray-700 hover:text-gray-300"
                  }`}
                  id={`slot_btn_${slot.number}`}
                >
                  <span>{slot.number}</span>
                  {slot.isOccupied && (
                    <span className="absolute bottom-0.5 right-0.5 h-1.5 w-1.5 rounded-full bg-purple-400"></span>
                  )}
                </button>
              ))}
            </div>

            {/* Bottom details of selected button */}
            {selectedSlot && (
              <div className="bg-[#181a24] p-4 rounded-xl border border-gray-800/80 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4" id="slots_detail_view">
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wider text-gray-500" id="detail_hdr">Свойства выбранной ячейки</h4>
                  <p className="text-lg font-extrabold text-white mt-1" id="detail_title">Пидараз #{selectedSlot.number}</p>
                  
                  {selectedSlot.isOccupied ? (
                    <div className="mt-2 text-xs space-y-1 text-gray-300" id="detail_body">
                      <div><span className="text-gray-500 font-mono">Никнейм в клике:</span> <span className="font-semibold text-white">{selectedSlot.firstName}</span></div>
                      <div>
                        <span className="text-gray-500 font-mono">Telegram ссылка:</span>{" "}
                        {selectedSlot.username ? (
                          <a 
                            href={`https://t.me/${selectedSlot.username}`} 
                            target="_blank" 
                            rel="noreferrer"
                            className="text-purple-400 hover:underline inline-flex items-center gap-1 inline font-mono"
                          >
                            @{selectedSlot.username}
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        ) : (
                          <span className="text-gray-500 font-mono italic">отсутствует (tg://user ID)</span>
                        )}
                      </div>
                      <div className="text-[10px] text-gray-500 mt-2 font-mono">
                        Зарегистрирован: {new Date(selectedSlot.registeredAt!).toLocaleString("ru-RU")}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500 italic mt-1.5" id="detail_empty_state">Эта роль свободна. Вы можете занять ее в форме симуляции или Telegram-боте.</p>
                  )}
                </div>

                <div className="w-full sm:w-auto self-stretch flex flex-col justify-between items-end border-t sm:border-t-0 border-gray-800 pt-3 sm:pt-0" id="telegram_msg_display">
                  <span className="text-[10px] font-mono text-gray-500 uppercase self-start sm:self-auto">telegram вывод в чате:</span>
                  <div className="bg-gray-900 border border-gray-800 px-3 py-2 rounded mt-2 w-full max-w-[280px] text-xs font-mono" id="tg_mock_bubble">
                    {selectedSlot.isOccupied ? (
                      <span className="text-gray-300">
                        🏳️‍🌈 Пидараз {selectedSlot.number} (
                        {selectedSlot.username ? `@${selectedSlot.username}` : selectedSlot.firstName}
                        ) на связи!
                      </span>
                    ) : (
                      <span className="text-gray-500 italic">Я безномерный пидараз 🤷‍♂️</span>
                    )}
                  </div>
                </div>
              </div>
            )}

          </div>

          {/* RIGHT: Module Code Tabs Viewer */}
          <div className="xl:col-span-5 bg-[#13151c] rounded-xl border border-gray-800 p-6 flex flex-col justify-between" id="code_panel">
            <div id="code_actions">
              <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4" id="code_header">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2" id="code_title">
                    💾 Готовые конфиги под интеграцию
                  </h2>
                  <p className="text-xs text-gray-400 mt-0.5" id="code_subtitle">Выбирайте библиотеку, которую использует ваш AdomBot</p>
                </div>
              </div>

              {/* Tabs list */}
              <div className="flex rounded-lg bg-gray-900 p-1 mb-4 border border-gray-800" id="tabs_group">
                <button
                  onClick={() => setActiveTab("telegraf")}
                  className={`flex-1 py-1.5 text-xs font-bold rounded-md transition ${
                    activeTab === "telegraf" 
                      ? "bg-purple-600 text-white" 
                      : "text-gray-400 hover:text-gray-300"
                  }`}
                  id="tab_telegraf_btn"
                >
                  Telegraf
                </button>
                <button
                  onClick={() => setActiveTab("grammy")}
                  className={`flex-1 py-1.5 text-xs font-bold rounded-md transition ${
                    activeTab === "grammy" 
                      ? "bg-purple-600 text-white" 
                      : "text-gray-400 hover:text-gray-300"
                  }`}
                  id="tab_grammy_btn"
                >
                  GrammY
                </button>
                <button
                  onClick={() => setActiveTab("node-telegram")}
                  className={`flex-1 py-1.5 text-xs font-bold rounded-md transition ${
                    activeTab === "node-telegram" 
                      ? "bg-purple-600 text-white" 
                      : "text-gray-400 hover:text-gray-300"
                  }`}
                  id="tab_node_telegram_btn"
                >
                  NT-Bot-API
                </button>
              </div>

              {/* Code viewer screen */}
              <div className="relative border border-gray-800 rounded-xl overflow-hidden bg-[#0d0e12] flex flex-col" id="code_view_container">
                <div className="bg-[#181a24] border-b border-gray-800 px-4 py-2 flex items-center justify-between" id="code_view_bar">
                  <div className="flex gap-1.5" id="window_controls">
                    <span className="h-3 w-3 rounded-full bg-red-400/80"></span>
                    <span className="h-3 w-3 rounded-full bg-yellow-400/80"></span>
                    <span className="h-3 w-3 rounded-full bg-green-400/80"></span>
                  </div>
                  <button 
                    onClick={() => handleCopyCode(getCodeStr()!)}
                    className="text-gray-400 hover:text-white transition flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700"
                    id="btn_copy_code"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3 w-3 text-green-400" />
                        <span>Скопировано!</span>
                      </>
                    ) : (
                      <>
                        <Clipboard className="h-3 w-3" />
                        <span>Копировать</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-4 text-xs font-mono text-gray-300 overflow-x-auto max-h-[340px] leading-relaxed" id="code_panel_output">
                  <code>{getCodeStr()}</code>
                </pre>
              </div>
            </div>

            {/* Quick Export instructions footer */}
            <div className="mt-6 pt-4 border-t border-gray-800 bg-[#181a24]/40 p-4 rounded-lg border border-gray-800/60" id="export_footer">
              <h4 className="text-xs font-bold text-white flex items-center gap-1.5 mb-1.5" id="exp_head">
                <BookOpen className="h-3.5 w-3.5 text-purple-400" />
                Как экспортировать файлы в AdomBot?
              </h4>
              <p className="text-[11px] text-gray-400 leading-relaxed" id="exp_body">
                Все необходимые для работы файлы уже добавлены в код проекта! Перейдите в верхнее меню настройки среды AI Studio и выберите <b>"Export to ZIP"</b> или <b>"Export to GitHub"</b>, чтобы вытащить модули <code className="text-purple-300 font-mono bg-purple-950/35 px-1 rounded">/src/bot</code> и импортировать их в ваш dev-репозиторий AdomBotBeta.
              </p>
            </div>

          </div>

        </div>

        {/* Security & DB instructions note */}
        <div className="mt-8 p-5 bg-gradient-to-r from-gray-900 to-[#121319] rounded-xl border border-gray-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4" id="bottom_instruction_alert">
          <div className="flex gap-3 items-start" id="bottom_instr_content">
            <div className="h-9 w-9 rounded-lg bg-yellow-950/40 border border-yellow-500/20 flex items-center justify-center p-2 mt-0.5" id="bi_icon_container">
              <ShieldAlert className="h-4 w-4 text-yellow-500" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white" id="bi_title">Безопасность и хранение данных</h4>
              <p className="text-xs text-gray-400 mt-1 max-w-3xl" id="bi_desc">
                Созданный класс <code className="text-yellow-400 font-mono bg-yellow-950/20 px-1 rounded">JsonFileStorage</code> использует локальный JSON-файл для надежного отслеживания занятых номеров и утренних чекинов. В модуле описана универсальная сигнатура <code className="text-yellow-400 font-mono bg-yellow-950/20 px-1 rounded">IBotStorage</code>, поэтому вы можете заменить файл-хранилище на PostgreSQL/Drizzle или MongoDB за 5 минут, не переписывая логику хэндлеров самого бота.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
