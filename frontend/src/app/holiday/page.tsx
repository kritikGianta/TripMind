import { redirect } from "next/navigation";

/** Book my holiday now lives on the Plan page, next to Plan a trip. */
export default function HolidayPage() {
  redirect("/plan?mode=holiday");
}
