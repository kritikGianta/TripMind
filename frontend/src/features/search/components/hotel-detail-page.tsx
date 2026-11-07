"use client";

import { useParams } from "next/navigation";

import { HotelDetailView } from "./hotel-detail";

/** Reads the route parameter on the client, so the page shell stays static. */
export function HotelDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <HotelDetailView id={id} />;
}
