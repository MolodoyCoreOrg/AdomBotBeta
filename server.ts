import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

// Lazy-initialized Gemini client with safety guards to preserve dev stability
function getGeminiClient() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || apiKey === "MY_GEMINI_API_KEY" || apiKey.trim() === "") {
    return null;
  }
  return new GoogleGenAI({
    apiKey: apiKey,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      }
    }
  });
}

// Fallback funny replies array to ensure app remains highly functional even if API key is not supplied
const fallbackReplies = [
  {
    word: "клаута",
    explanation: "'Клаут' (clout) — сленг, в данном контексте может означать влияние/статус, достигнутый через психотропное расширение сознания, и поэтому требует немедленного заглушения как часть скрытой наркотематики.",
    duration: "420 секунд"
  },
  {
    word: "соль",
    explanation: "'Соль' — в быту приправа, однако в современном контексте является прямым триггером опасных синтетических катинонов. Модератор считает употребление слова в супе подозрительным.",
    duration: "2 часа"
  },
  {
    word: "флексить",
    explanation: "'Флекс' — указывает на неестественные изгибы тела под воздействием стимуляторов. Попытка зафлексить перед ботом карается профилактическим баном.",
    duration: "15 минут"
  },
  {
    word: "живешь",
    explanation: "'Жить' в контексте жизни ради чего-то намекает на кайф, трипы и гедонизм. Гедонистический образ жизни признан пропагандой легких наркотиков.",
    duration: "30 минут за гедонизм"
  },
  {
    word: "чай",
    explanation: "'Чай' — может служить прикрытием для употребления сушеного запрещенного сырья в пакетиках. Бот превентивно защищает чат.",
    duration: "до остывания чайника"
  },
  {
    word: "код",
    explanation: "'Код' — созвучно с 'кодеин', популярным аптечным сиропом. Программирование расценивается как латентная пропаганда кодеиновой зависимости.",
    duration: "до компиляции без ошибок"
  }
];

// Helper to extract a word if we end up generating the default payload or need fallback choice
function getPresetFallback(message: string) {
  const lower = message.toLowerCase();
  for (const item of fallbackReplies) {
    if (lower.includes(item.word)) {
      return item;
    }
  }
  // If nothing matches, take a random one but swap the "word" with a random word from the user's message
  const words = message.split(/\s+/).filter(w => w.length > 3);
  const randomFallback = fallbackReplies[Math.floor(Math.random() * fallbackReplies.length)];
  const targetWord = words.length > 0 ? words[Math.floor(Math.random() * words.length)] : "слова";
  return {
    word: targetWord.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g, ""),
    explanation: randomFallback.explanation.replace(new RegExp(randomFallback.word, 'gi'), targetWord),
    duration: randomFallback.duration
  };
}

// API: Handle drug propaganda trigger logic (Gemini dynamic response or presets fallback)
app.post("/api/analyze-message", async (req, res) => {
  const { message } = req.body;
  if (!message || message.trim() === "") {
    return res.status(400).json({ error: "Сообщение не должно быть пустым!" });
  }

  const ai = getGeminiClient();
  if (!ai) {
    // Return mock hilarious result
    console.log("Gemini API key is not set. Responding with clever fallback.");
    const result = getPresetFallback(message);
    return res.json({
      success: true,
      results: result,
      source: "fallback"
    });
  }

  try {
    const prompt = `Пользователь написал в чат: "${message}".
Твоя задача: найти ОДНО слово в этом сообщении и забавно/абсурдно притянуть его за уши к теме наркотиков, заявляя, что это слово является скрытой пропагандой наркотиков (или сленгом наркоманов/дилеров, или вызывает запрещенные ассоциации).
Будь креативным, пиши очень иронично, в умном, строгом, канцелярском стиле борца с наркотиками, который везде видит заговор. Напиши краткое смешное обоснование и выпиши длительность мута.
Пример:
Слово: "клаута"
Объяснение: "'Клаут' (clout) — сленг, в данном контексте может означать влияние/статус, достигнутый через наркотики, но требует заглушения как часть наркотематики."
Длительность: "420 секунд"`;

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
      config: {
        systemInstruction: "Вы — юмористический модератор Telegram-бота AdomBot. Ваша единственная цель — выдумывать абсурдные обвинения в пропаганде наркотиков на ровном месте для любых человеческих слов. Возвращайте строгий структурированный JSON.",
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            word: {
              type: Type.STRING,
              description: "The word chosen out of the message to mute"
            },
            explanation: {
              type: Type.STRING,
              description: "Detailed extremely funny pseudo-intellectual drug propaganda explanation in Russian"
            },
            duration: {
              type: Type.STRING,
              description: "Funny specific muting duration, e.g. 420 секунд, 10 минут за флекс"
            }
          },
          required: ["word", "explanation", "duration"]
        }
      }
    });

    const text = response.text?.trim() || "{}";
    const data = JSON.parse(text);

    return res.json({
      success: true,
      results: data,
      source: "gemini"
    });
  } catch (error: any) {
    console.error("Gemini API Error:", error);
    // Graceful fallback on API errors
    const result = getPresetFallback(message);
    return res.json({
      success: true,
      results: result,
      source: "fallback_error",
      errorMsg: error.message
    });
  }
});

// Mock Database of users for the Pidoras Tally / Inline game in the UI
const mockedUsers = [
  { id: 101, username: "rayka", first_name: "Раиса", count: 12, rating: 98 },
  { id: 102, username: "vlad_core", first_name: "Влад", count: 32, rating: 15 },
  { id: 103, username: "molodoy_dev", first_name: "Молодой", count: 24, rating: 44 },
  { id: 104, username: "clout_chaser", first_name: "КлаутХантер", count: 8, rating: 89 },
  { id: 105, username: "skater_boy", first_name: "Антон", count: 15, rating: 67 }
];

app.get("/api/pidor-stats", (req, res) => {
  res.json({
    users: mockedUsers,
    totalRounds: 91
  });
});

// Vite middleware & Static SPA Serving Setup
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running at http://localhost:${PORT}`);
  });
}

startServer();
