// Типы ответов API (см. docs/architecture.md). Деньги приходят строками-десятичными.

export type Role = "owner" | "manager" | "admin";

export type BookingStatus =
  | "awaiting_payment"
  | "awaiting_confirmation"
  | "confirmed"
  | "checked_in"
  | "checked_out"
  | "closed"
  | "cancelled"
  | "expired"
  | "blocked";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  account_id: number | null;
  account_slug: string | null;
  account_name: string | null;
  telegram_linked: boolean;
}

export interface Photo {
  id: number;
  path: string;
  position: number;
}

export interface Apartment {
  id: number;
  slug: string;
  title: string;
  district: string;
  address: string;
  description: string;
  amenities: string[];
  rules: string;
  checkin_instructions: string;
  price_per_night: string;
  weekend_price: string | null;
  min_nights: number;
  max_guests: number;
  check_in_time: string;
  check_out_time: string;
  prepayment: string;
  deposit: string;
  free_cancel_days: number;
  is_active: boolean;
  photos: Photo[];
}

export interface PublicApartmentCard {
  slug: string;
  title: string;
  district: string;
  price_per_night: string;
  rating: number | null;
  reviews_count: number;
  cover: string | null;
}

export interface PublicAccount {
  slug: string;
  name: string;
  apartments: PublicApartmentCard[];
}

export interface PublicReview {
  rating: number;
  text: string;
  owner_reply: string | null;
  guest_name: string;
  created_at: string;
}

export interface PublicApartment {
  slug: string;
  title: string;
  district: string;
  lat: string | null;
  lng: string | null;
  description: string;
  amenities: string[];
  rules: string;
  price_per_night: string;
  weekend_price: string | null;
  min_nights: number;
  max_guests: number;
  check_in_time: string;
  check_out_time: string;
  prepayment: string;
  deposit: string;
  free_cancel_days: number;
  photos: string[];
  rating: number | null;
  reviews: PublicReview[];
  busy: { start_at: string; end_at: string }[];
}

export interface Quote {
  nights: number;
  total: string;
  prepayment: string;
  deposit: string;
  breakdown: { night: string; price: string; kind: "regular" | "weekend" | "special" }[];
}

export interface GuestBooking {
  token: string;
  status: BookingStatus;
  apartment_title: string;
  check_in: string;
  check_out: string;
  guests_count: number;
  total_price: string;
  prepayment_amount: string;
  deposit_amount: string;
  hold_expires_at: string | null;
  payment_details: string | null;
  payment_qr: string | null;
  address: string | null;
  checkin_instructions: string | null;
  reject_reason: string | null;
  can_cancel: boolean;
  free_cancel_until: string;
  can_review: boolean;
}

export interface Guest {
  id: number;
  name: string;
  phone: string;
  notes: string;
  is_blacklisted: boolean;
  blacklist_reason: string | null;
}

export interface GuestRow extends Guest {
  bookings: number;
  total_spent: string;
}

export interface BookingEvent {
  from_status: string | null;
  to_status: string;
  actor: string;
  note: string | null;
  created_at: string;
}

export interface Booking {
  id: number;
  apartment_id: number;
  guest: Guest | null;
  start_at: string;
  end_at: string;
  guests_count: number;
  status: BookingStatus;
  source: string;
  total_price: string;
  prepayment_amount: string;
  deposit_amount: string;
  balance_paid: boolean;
  deposit_status: "none" | "received" | "returned" | "withheld";
  deposit_withheld: string;
  deposit_note: string | null;
  hold_expires_at: string | null;
  has_receipt: boolean;
  reject_reason: string | null;
  cancel_reason: string | null;
  refund_due: boolean;
  refunded: boolean;
  block_reason: string | null;
  created_at: string;
}

export interface BookingDetail extends Booking {
  events: BookingEvent[];
  guest_link: string;
}

export interface CalendarBooking {
  id: number;
  status: BookingStatus;
  start_at: string;
  end_at: string;
  guest: string | null;
  block_reason: string | null;
  warning: boolean;
}

export interface CalendarData {
  from: string;
  to: string;
  apartments: { id: number; title: string; bookings: CalendarBooking[] }[];
}

export interface Analytics {
  from: string;
  to: string;
  days: number;
  totals: {
    occupancy_pct: number;
    nights: number;
    revenue: string;
    expenses: string;
    profit: string;
    avg_night_price: string | null;
    bookings_created: number;
    cancelled_pct: number;
    expired_pct: number;
  };
  apartments: {
    apartment_id: number;
    title: string;
    nights: number;
    revenue: string;
    expenses: string;
    profit: string;
    occupancy_pct: number;
    avg_night_price: string | null;
  }[];
  sources: { source: string; bookings: number; revenue: string }[];
}

export interface Expense {
  id: number;
  apartment_id: number;
  category: "cleaning" | "utilities" | "repair" | "supplies" | "other";
  amount: string;
  spent_on: string;
  note: string;
}

export interface Review {
  id: number;
  booking_id: number;
  apartment_id: number;
  apartment_title: string;
  guest_name: string;
  rating: number;
  text: string;
  owner_reply: string | null;
  created_at: string;
}

export interface Notification {
  id: number;
  booking_id: number | null;
  kind: string;
  text: string;
  is_read: boolean;
  created_at: string;
}

export interface AccountSettings {
  name: string;
  slug: string;
  payment_details: string;
  payment_qr: string | null;
}
