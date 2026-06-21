/**
 * Types representing the Pidaraz Recount Bot system.
 */

export interface TeleUser {
  id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  slotNumber?: number; // Chosen number (1-100)
  registeredAt?: string;
  lastCheckIn?: string; // Date string of last morning check-in
}

export interface Slot {
  number: number;
  userId?: number;
  occupiedAt?: string;
}

export interface RecountState {
  users: Record<number, TeleUser>; // userId -> TeleUser
  slots: Record<number, Slot>;     // slotNumber -> Slot
  activeRecountDate?: string;      // Current active check-in date
  checkIns: Record<string, number[]>; // date -> list of userIds who checked in
}
