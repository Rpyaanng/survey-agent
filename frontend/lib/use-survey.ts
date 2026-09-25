"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";
import type { Survey } from "./types";

export function useSurveyId() {
  return useParams<{ id: string }>().id;
}

export function useSurvey() {
  const id = useSurveyId();
  const swr = useSWR<Survey>(id ? `/surveys/${id}` : null);
  return { id, survey: swr.data, ...swr };
}
