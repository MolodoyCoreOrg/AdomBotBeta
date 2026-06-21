import * as fs from 'fs';
import * as path from 'path';
import { RecountState, TeleUser, Slot } from './types';

export interface IBotStorage {
  getUser(userId: number): Promise<TeleUser | null>;
  saveUser(user: TeleUser): Promise<void>;
  chooseSlot(userId: number, username: string | undefined, firstName: string, lastName: string | undefined, slotNumber: number): Promise<{ success: boolean; error?: string }>;
  getSlots(limit: number): Promise<Slot[]>;
  getAllUsers(): Promise<TeleUser[]>;
  recordCheckIn(userId: number, dateStr: string): Promise<boolean>;
  getCheckIns(dateStr: string): Promise<number[]>;
}

export class JsonFileStorage implements IBotStorage {
  private filePath: string;
  private state: RecountState;
  private maxSlots: number;

  constructor(filePath?: string, maxSlots = 100) {
    this.filePath = filePath || path.join(process.cwd(), 'recount-data.json');
    this.maxSlots = maxSlots;
    this.state = this.loadState();
  }

  private loadState(): RecountState {
    try {
      if (fs.existsSync(this.filePath)) {
        const fileContent = fs.readFileSync(this.filePath, 'utf-8');
        const parsed = JSON.parse(fileContent) as RecountState;
        
        // Ensure slots structure is fully populated
        if (!parsed.slots) parsed.slots = {};
        if (!parsed.users) parsed.users = {};
        if (!parsed.checkIns) parsed.checkIns = {};
        
        // Populate slots up to maxSlots
        for (let i = 1; i <= this.maxSlots; i++) {
          if (!parsed.slots[i]) {
            parsed.slots[i] = { number: i };
          }
        }
        return parsed;
      }
    } catch (e) {
      console.error("Error reading storage file, initializing fresh state", e);
    }

    // Initialize fresh state
    const slots: Record<number, Slot> = {};
    for (let i = 1; i <= this.maxSlots; i++) {
      slots[i] = { number: i };
    }
    return {
      users: {},
      slots: slots,
      checkIns: {}
    };
  }

  private saveState(): void {
    try {
      fs.writeFileSync(this.filePath, JSON.stringify(this.state, null, 2), 'utf-8');
    } catch (e) {
      console.error("Error writing storage file", e);
    }
  }

  async getUser(userId: number): Promise<TeleUser | null> {
    return this.state.users[userId] || null;
  }

  async saveUser(user: TeleUser): Promise<void> {
    this.state.users[user.id] = {
      ...this.state.users[user.id],
      ...user
    };
    this.saveState();
  }

  async chooseSlot(
    userId: number, 
    username: string | undefined, 
    firstName: string, 
    lastName: string | undefined, 
    slotNumber: number
  ): Promise<{ success: boolean; error?: string }> {
    if (slotNumber < 1 || slotNumber > this.maxSlots) {
      return { success: false, error: `Номер должен быть в пределах от 1 до ${this.maxSlots}!` };
    }

    const user = this.state.users[userId];
    if (user && user.slotNumber !== undefined) {
      return { success: false, error: `Вы уже выбрали номер — это Пидараз ${user.slotNumber}. Изменить его нельзя!` };
    }

    const slot = this.state.slots[slotNumber];
    if (slot && slot.userId !== undefined && slot.userId !== userId) {
      return { success: false, error: `Номер ${slotNumber} уже занят другими пидаразом!` };
    }

    // Assign the slot
    const nowStr = new Date().toISOString();
    
    // Create/update user object
    const updatedUser: TeleUser = {
      id: userId,
      username: username,
      first_name: firstName,
      last_name: lastName,
      slotNumber: slotNumber,
      registeredAt: nowStr
    };

    this.state.users[userId] = updatedUser;
    this.state.slots[slotNumber] = {
      number: slotNumber,
      userId: userId,
      occupiedAt: nowStr
    };

    this.saveState();
    return { success: true };
  }

  async getSlots(limit = 100): Promise<Slot[]> {
    const slots: Slot[] = [];
    for (let i = 1; i <= limit; i++) {
      slots.push(this.state.slots[i] || { number: i });
    }
    return slots;
  }

  async getAllUsers(): Promise<TeleUser[]> {
    return Object.values(this.state.users);
  }

  async recordCheckIn(userId: number, dateStr: string): Promise<boolean> {
    const user = this.state.users[userId];
    if (!user) return false;

    if (!this.state.checkIns[dateStr]) {
      this.state.checkIns[dateStr] = [];
    }

    if (!this.state.checkIns[dateStr].includes(userId)) {
      this.state.checkIns[dateStr].push(userId);
      user.lastCheckIn = dateStr;
      this.saveState();
      return true;
    }

    return false;
  }

  async getCheckIns(dateStr: string): Promise<number[]> {
    return this.state.checkIns[dateStr] || [];
  }
}
