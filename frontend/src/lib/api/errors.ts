/**
 * Every API failure becomes an `ApiError` carrying the backend's stable error `code`.
 * User-facing copy is chosen here, by code, so components never parse server messages.
 */

export type FieldError = { field: string; message: string; type: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;
  readonly requestId: string | undefined;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    details?: Record<string, unknown>;
    requestId?: string;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details;
    this.requestId = init.requestId;
  }

  get fieldErrors(): FieldError[] {
    const fields = this.details?.["fields"];
    return Array.isArray(fields) ? (fields as FieldError[]) : [];
  }
}

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "Email or password is incorrect.",
  EMAIL_TAKEN: "An account with this email already exists.",
  ACCOUNT_DISABLED: "This account has been disabled.",
  RATE_LIMITED: "Too many attempts. Please wait a minute and try again.",
  FEATURE_DISABLED: "This feature is not available right now.",
  DEMO_ACCOUNT_MISSING: "Demo accounts are not set up yet.",
  SESSION_EXPIRED: "Your session has ended. Please sign in again.",
  SESSION_REVOKED: "Your session has ended. Please sign in again.",
  NETWORK_ERROR: "We couldn't reach TripMind. Check your connection and try again.",
  INTERNAL: "Something went wrong on our side. Please try again.",
  DATE_IN_PAST: "That date has already passed. Choose a later date.",
  RETURN_BEFORE_DEPARTURE: "The return date must be on or after the departure date.",
  SAME_LOCATION: "Origin and destination must be different.",
  LOCATION_NOT_FOUND: "We couldn't find that place in the current dataset.",
  INVALID_STAY: "Check the dates and the number of rooms and guests.",
  STAY_TOO_LONG: "Stays can be up to 30 nights.",
  HOTEL_NOT_FOUND: "This stay is no longer available.",
  FORBIDDEN: "You don't have access to this page.",
  IMPORT_IN_PROGRESS: "Another import is running. Try again when it finishes.",
  PAYLOAD_TOO_LARGE: "The file is too large.",
  SOLD_OUT: "Sorry, that just sold out for your party. Please choose another option.",
  PRICE_CHANGED: "The price changed while you were checking out.",
  OFFER_UNAVAILABLE: "This option is no longer available.",
  OFFER_NOT_BOOKABLE: "This option can't be booked because the data has no price for it.",
  ROOM_TOO_SMALL: "This room doesn't fit your party.",
  TRAVELLERS_MISMATCH: "Enter details for every traveller.",
  CARD_DECLINED: "Your card was declined. Try another card.",
  INSUFFICIENT_FUNDS: "The card has insufficient funds. Try another card.",
  CARD_INVALID: "That card number isn't valid.",
  CARD_EXPIRED: "That card has expired.",
  HOLD_EXPIRED: "Your hold expired. Please search again.",
  BOOKING_NOT_PAYABLE: "This booking can no longer be paid.",
  NOTHING_TO_CANCEL: "There's nothing left to cancel.",
  BOOKING_NOT_FOUND: "Booking not found.",
  TRIP_NOT_FOUND: "Trip not found.",
  PLAN_NOT_FOUND: "Plan not found.",
  OPTION_NOT_FOUND: "That option is no longer available.",
  CASE_NOT_FOUND: "This recovery case was not found.",
  CASE_RESOLVED: "This has already been sorted.",
  ALREADY_DISRUPTED: "That flight is already cancelled.",
  FLIGHT_NOT_FOUND: "Flight not found.",
  PROFILE_LIMIT: "You can save up to 10 travellers.",
  PROFILE_NOT_FOUND: "That traveller was not found.",
  PROMO_INVALID: "This promo code can't be used.",
  PROMO_ALREADY_USED: "You've already used this promo code.",
  GROUP_NOT_FOUND: "This group doesn't exist or you're not a member.",
  INVITE_INVALID: "This invite link isn't valid.",
  GROUP_DECIDED: "This group has already decided.",
  GROUP_FULL: "This group is full.",
  OWNER_CANNOT_LEAVE: "The organiser can't leave their own group.",
  PLAN_EMPTY: "This plan has no options to share.",
  ACCOUNT_LOCKED: "Too many failed attempts. Try again in a few minutes.",
  ACCOUNT_HAS_UPCOMING_TRIPS: "You have upcoming trips. Cancel them before deleting your account.",
  WRONG_PASSWORD: "That password isn't right.",
  RESET_TOKEN_INVALID: "This reset link has expired or was already used. Ask for a new one.",
  DEMO_ACCOUNT: "The demo account can't be changed. Create your own account to try this.",
  CANNOT_CHANGE_SELF: "You can't disable your own account.",
  USER_NOT_FOUND: "That account was not found.",
  ALERT_LIMIT: "You've reached the limit for price alerts. Stop one to add another.",
  ALERT_NOTHING_TO_WATCH: "There's no price to watch for this search yet.",
  ALERT_NOT_FOUND: "That price alert was not found.",
  ALERT_TARGET_MET: "It's already at or below that price.",
  SAVED_LIMIT: "You've saved the maximum number of stays. Remove one to add another.",
  SEARCH_NOT_FOUND: "That search is no longer in your history.",
  CHANGE_NOT_ALLOWED: "This can't be changed any more.",
  CHANGE_PRICE_CHANGED: "The price changed. Check the new cost and confirm again.",
  NOTHING_TO_CHANGE: "That's the same as what you already have.",
  PAYMENT_REQUIRED: "Enter your card details to pay the difference.",
  PAYMENT_DECLINED: "Your card was declined. Try another card.",
  EXTRAS_CLOSED: "Seats and extras are closed for this flight.",
  EXTRAS_PRICE_CHANGED: "A price changed. Check the new total and confirm again.",
  EXTRA_UNKNOWN: "That option is no longer offered.",
  SEAT_TAKEN: "Someone just took that seat. Please pick another.",
  SEAT_UNKNOWN: "That seat doesn't exist on this aircraft.",
  FLIGHT_GONE: "That flight is no longer available.",
  FLIGHT_NOT_IN_ITEM: "That flight isn't part of this booking.",
  TRAVELLER_NOT_IN_BOOKING: "That traveller isn't on this booking.",
  ITEM_NOT_FOUND: "That part of the booking was not found.",
  NOT_A_FLIGHT: "This option only applies to flights.",
  NOT_A_STAY: "This option only applies to stays.",
  REVIEW_EXISTS: "You've already reviewed this stay.",
  REVIEW_TOO_EARLY: "You can review this stay after you check out.",
  REVIEW_WINDOW_CLOSED: "The time to review this stay has passed.",
  REVIEW_NOT_ALLOWED: "Only guests who stayed can review.",
  REVIEW_CONTENT: "Please remove personal details or unsuitable language from your review.",
  REVIEW_NOT_FOUND: "That review was not found.",
  TICKET_NOT_FOUND: "That request was not found.",
  TICKET_CLOSED: "This request is closed. Start a new one if you need more help.",
  TICKET_LIMIT: "You have many open requests. Close one before adding another.",
  CATEGORY_UNKNOWN: "That category isn't recognised.",
  ROOM_NOT_FOUND: "That room is no longer available.",
  SAME_ORIGIN_DESTINATION: "Origin and destination must be different.",
  OFFER_INVALID: "This option is no longer available. Please search again.",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message ?? MESSAGES.INTERNAL;
  }
  return MESSAGES.INTERNAL;
}
