// @ts-nocheck
import { Telegraf, Markup } from 'telegraf';
import { JsonFileStorage, IBotStorage } from './storage';
import { TeleUser } from './types';

/**
 * Implementation of "Pidaraz Recount Bot" using the Telegraf framework.
 * 
 * Features:
 * - /start to welcome and guide user
 * - Simply message a number (1-100) to register
 * - /list to see all occupied slots with links to profiles
 * - Inline queries to share status in any chat
 * - Daily morning check-in notification & global broadcasts
 */

export class TelegrafRecountBot {
  private bot: Telegraf;
  private storage: IBotStorage;
  private maxSlots = 100;

  constructor(token: string, storage?: IBotStorage) {
    this.bot = new Telegraf(token);
    this.storage = storage || new JsonFileStorage(undefined, this.maxSlots);
    this.setupHandlers();
  }

  private setupHandlers() {
    // 1. START Command
    this.bot.command('start', async (ctx) => {
      const userId = ctx.from.id;
      const user = await this.storage.getUser(userId);

      const welcomeText = 
        `🏳️‍🌈 *Добро пожаловать в Пересчет Пидаразов!*\n\n` +
        `Здесь ты можешь занять свой уникальный пожизненный номер пидараза (от 1 до ${this.maxSlots}).\n\n` +
        `⚠️ *Правила просты:*\n` +
        `1. Номер выбирается ОДИН раз и изменить его нельзя.\n` +
        `2. Занятый номер никто другой забрать не сможет.\n` +
        `3. Всего доступно ровно ${this.maxSlots} слотов.\n\n` +
        `👇 Как занять номер?\n` +
        `Просто напиши в чат любое число от 1 до ${this.maxSlots}.`;

      if (user && user.slotNumber !== undefined) {
        await ctx.replyWithMarkdownV2(
          `🏳️‍🌈 *Вы уже в системе\\!*\n\nВаш номер: *Пидараз ${user.slotNumber}*\\.\n\n` +
          `Теперь вы можете использовать этого бота в любом чате\\! Просто введите:\n` +
          `\`@${ctx.botInfo.username}\` и выберите вариант отправки\\.`
        );
        return;
      }

      await ctx.replyWithMarkdownV2(
        welcomeText.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&'), // escape for MarkdownV2
        Markup.inlineKeyboard([
          Markup.button.callback('Посмотреть список занятых', 'show_occupied_list'),
        ])
      );
    });

    // 2. LIST Command
    this.bot.command('list', async (ctx) => {
      await this.sendOccupiedListByCtx(ctx);
    });

    // Callback query for viewing the occupied list
    this.bot.action('show_occupied_list', async (ctx) => {
      await ctx.answerCbQuery();
      await this.sendOccupiedListByCtx(ctx);
    });

    // Admin trigger command for morning recount test
    this.bot.command('morning_recount_admin', async (ctx) => {
      // Check if user is admin (optional, can be modified by user)
      await ctx.reply('Запускаю утренний пересчет пидаразов...');
      await this.triggerMorningRecount();
      await ctx.reply('Рассылка запущена!');
    });

    // 3. Number Selection - listening to raw text input
    this.bot.on('text', async (ctx) => {
      const userId = ctx.from.id;
      const text = ctx.message.text.trim();
      const num = parseInt(text, 10);

      // Check if input is a valid number query
      if (isNaN(num)) {
        // If not a number, maybe they typed some other command, just reply instructions
        const user = await this.storage.getUser(userId);
        if (!user || user.slotNumber === undefined) {
          await ctx.reply(`Чтобы зарегистрироваться, просто отправь мне число от 1 до ${this.maxSlots}. Например: 7`);
        }
        return;
      }

      // Try assigning slot
      const result = await this.storage.chooseSlot(
        userId,
        ctx.from.username,
        ctx.from.first_name,
        ctx.from.last_name,
        num
      );

      if (result.success) {
        const escapedUser = this.escapeMarkdownV2(ctx.from.first_name);
        await ctx.replyWithMarkdownV2(
          `🎉 *Поздравляем\\, ${escapedUser}\\!*\n\n` +
          `Вы успешно зарезервировали слот \\#*${num}*\\.\n` +
          `Отныне и вовек вы зафиксированы как *Пидараз ${num}*\\!\n\n` +
          `Теперь используйте бота в любых чатах через inline\\-режим:\n` +
          `Введите \`@${ctx.botInfo?.username || 'bot'}\` в поле ввода сообщения в любом чате\\.`
        );
      } else {
        await ctx.reply(`❌ Ошибка: ${result.error}`);
      }
    });

    // 4. Callback Query for Morning Check-in Button
    this.bot.action(/^checkin_(\d+)$/, async (ctx) => {
      const slotNum = parseInt(ctx.match[1], 10);
      const userId = ctx.from.id;
      const dateStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

      const user = await this.storage.getUser(userId);
      if (!user || user.slotNumber !== slotNum) {
        await ctx.answerCbQuery('Это не твой номер или ты не зарегистрирован!', { show_alert: true });
        return;
      }

      const registeredCheckIn = await this.storage.recordCheckIn(userId, dateStr);
      if (!registeredCheckIn) {
        await ctx.answerCbQuery('Вы уже отметились сегодня как "на связи"!', { show_alert: true });
        return;
      }

      await ctx.answerCbQuery('Вы успешно подтвердили свое присутствие!', { show_alert: false });
      
      // Update the inline dynamic message to confirm checked in status of this button
      await ctx.editMessageText(
        `✅ Пидараз ${slotNum} на связи! Присутствие подтверждено.`
      );

      // Broadcast to all users of the bot that "Пидараз N на связи!"
      const allUsers = await this.storage.getAllUsers();
      const userMention = user.username 
        ? `@${user.username}` 
        : `[${user.first_name}](tg://user?id=${user.id})`;

      const broadcastText = `📣 *Пересчет:* Пидараз *${slotNum}* (${userMention}) на связи!`;

      // Perform broadcast
      let successCount = 0;
      for (const recipient of allUsers) {
        try {
          // Avoid self-notifying via broadcast if they just clicked it
          await this.bot.telegram.sendMessage(recipient.id, broadcastText, { parse_mode: 'Markdown' });
          successCount++;
        } catch (e) {
          // Could be blocked or inactive
        }
      }
      console.log(`Broadcast for Pidaraz ${slotNum} completed. Delivered to ${successCount} users.`);
    });

    // 5. INLINE Query handler
    this.bot.on('inline_query', async (ctx) => {
      const userId = ctx.from.id;
      const user = await this.storage.getUser(userId);
      const botUsername = ctx.botInfo.username;

      if (user && user.slotNumber !== undefined) {
        const slotNum = user.slotNumber;
        const userMention = user.username 
          ? `@${user.username}` 
          : `[${user.first_name}](tg://user?id=${user.id})`;

        const messageText = `🏳️‍🌈 Пидараз ${slotNum} (${userMention}) на связи!`;

        await ctx.answerInlineQuery([
          {
            type: 'article',
            id: `pidaraz_present_${slotNum}`,
            title: 'Пересчет пидаразов',
            description: `Отправить: "Пидараз ${slotNum} на связи"`,
            input_message_content: {
              message_text: messageText,
              parse_mode: 'Markdown'
            }
          }
        ], { is_personal: true, cache_time: 0 });
      } else {
        // User has not chosen a number yet
        const startLink = `https://t.me/${botUsername}?start=choose`;
        await ctx.answerInlineQuery([
          {
            type: 'article',
            id: 'no_number_error',
            title: 'Я безномерный пидараз 🤷‍♂️',
            description: 'Вы ещё не выбрали номер. Нажмите здесь, чтобы выбрать номер.',
            input_message_content: {
              message_text: 'Я безномерный пидараз... 🤷‍♂️\n\nМне нужно зайти в бота и зарезервировать свой номер пидараза!',
              parse_mode: 'Markdown'
            },
            reply_markup: {
              inline_keyboard: [
                [
                  { text: 'Выбрать номер 🏳️‍🌈', url: startLink }
                ]
              ]
            }
          }
        ], { is_personal: true, cache_time: 0 });
      }
    });
  }

  /**
   * Helper to fetch and format list of occupied slots using current context
   */
  private async sendOccupiedListByCtx(ctx: any) {
    const slots = await this.storage.getSlots(this.maxSlots);
    const users = await this.storage.getAllUsers();
    
    // Create map for rapid lookup
    const userMap = new Map<number, TeleUser>();
    users.forEach(u => userMap.set(u.id, u));

    const occupiedSlots = slots.filter(s => s.userId !== undefined);

    if (occupiedSlots.length === 0) {
      await ctx.reply(
        `📭 Все слоты свободны!\n` +
        `Будь первым! Напиши число от 1 до ${this.maxSlots}, чтобы зарезервировать номер.`
      );
      return;
    }

    let report = `🏳️‍🌈 *Список зарегистрированных пидаразов (${occupiedSlots.length}/${this.maxSlots}):*\n\n`;

    for (const slot of occupiedSlots) {
      const u = userMap.get(slot.userId!);
      if (u) {
        const mention = u.username 
          ? `[@${u.username}](https://t.me/${u.username})` 
          : `[${u.first_name}](tg://user?id=${u.id})`;
        
        report += `• *Пидараз ${slot.number}* — ${mention} на связи\n`;
      }
    }

    await ctx.reply(report, { parse_mode: 'Markdown', disable_web_page_preview: true });
  }

  /**
   * Trigger morning recount: Ping all registered users
   */
  public async triggerMorningRecount() {
    const users = await this.storage.getAllUsers();
    const registeredUsers = users.filter(u => u.slotNumber !== undefined);

    console.log(`Starting morning recount check-in for ${registeredUsers.length} registered users...`);

    for (const u of registeredUsers) {
      try {
        const text = `⏰ *ПЕРЕСЧЕТ ПИДАРАЗОВ!*\n\nПидараз *${u.slotNumber}* на связи??? Подтверди присутствие!`;
        await this.bot.telegram.sendMessage(u.id, text, {
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard([
            Markup.button.callback(`🙋‍♂️ Пидараз ${u.slotNumber} на связи!`, `checkin_${u.slotNumber}`)
          ])
        });
      } catch (err) {
        console.error(`Failed to trigger check-in notification for user ${u.id}:`, err);
      }
    }
  }

  public getBotInstance(): Telegraf {
    return this.bot;
  }

  private escapeMarkdownV2(text: string): string {
    return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
  }

  /**
   * Launch bot
   */
  public launch() {
    this.bot.launch().then(() => {
      console.log('Telegram Recount Bot successfully launched!');
    }).catch(err => {
      console.error('Error launching Telegraf bot:', err);
    });

    // Enable graceful stop
    process.once('SIGINT', () => this.bot.stop('SIGINT'));
    process.once('SIGTERM', () => this.bot.stop('SIGTERM'));
  }
}
