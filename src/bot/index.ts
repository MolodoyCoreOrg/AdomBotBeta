import { TelegrafRecountBot } from './telegraf-bot';
import { GrammyRecountBot } from './grammy-bot';
import { NodeTelegramRecountBot } from './node-telegram-bot-api';
import { JsonFileStorage } from './storage';

/**
 * Entry point file showing how to initialize and launch each type of bot,
 * and how to set up the daily morning recount schedule.
 */

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;

if (!TOKEN) {
  console.warn("⚠️ TELEGRAM_BOT_TOKEN is not defined in the environment variables!");
}

// 1. Example using Telegraf framework
export function startTelegrafVersion() {
  if (!TOKEN) return;
  console.log("Initializing Telegraf Recount Bot...");
  
  const storage = new JsonFileStorage();
  const bot = new TelegrafRecountBot(TOKEN, storage);
  
  // Start polling
  bot.launch();

  // Schedule daily check-in (e.g. every morning at 09:00 AM)
  setupDailyCron(() => {
    bot.triggerMorningRecount();
  });
}

// 2. Example using GrammY framework
export function startGrammyVersion() {
  if (!TOKEN) return;
  console.log("Initializing GrammY Recount Bot...");
  
  const storage = new JsonFileStorage();
  const bot = new GrammyRecountBot(TOKEN, storage);
  
  // Start polling
  bot.launch();

  // Schedule daily check-in (e.g. every morning at 09:00 AM)
  setupDailyCron(() => {
    bot.triggerMorningRecount();
  });
}

// 3. Example using node-telegram-bot-api
export function startNodeTelegramVersion() {
  if (!TOKEN) return;
  console.log("Initializing node-telegram-bot-api Recount Bot...");
  
  const storage = new JsonFileStorage();
  const bot = new NodeTelegramRecountBot(TOKEN, storage);
  
  // Start polling has been initiated inside construction
  console.log("node-telegram-bot-api Recount Bot is listening...");

  // Schedule daily check-in (e.g. every morning at 09:00 AM)
  setupDailyCron(() => {
    bot.triggerMorningRecount();
  });
}

/**
 * A standard, dependency-free helper to schedule a callback at a specific hour
 * (e.g. every morning at 9:00 AM localized).
 * You can replace this with 'node-cron' or any other package if they are installed in your project.
 */
function setupDailyCron(callback: () => void, targetHour = 9, targetMinute = 0) {
  console.log(`Setting up daily recounts at ${targetHour.toString().padStart(2, '0')}:${targetMinute.toString().padStart(2, '0')} daily.`);
  
  function checkTime() {
    const now = new Date();
    if (now.getHours() === targetHour && now.getMinutes() === targetMinute) {
      try {
        callback();
      } catch (err) {
        console.error("Error executing scheduled morning recount:", err);
      }
    }
  }

  // Check every minute
  setInterval(checkTime, 60000);
}
export { JsonFileStorage };
export { TelegrafRecountBot };
export { GrammyRecountBot };
export { NodeTelegramRecountBot };
