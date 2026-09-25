"use client";

import { useEffect, useRef, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { Loader2, Mic, MicOff, PhoneOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PublicSurvey, TranscriptTurn } from "@/lib/types";

interface VoiceSession {
  response_id: string;
  response_token: string;
  signed_url: string;
  dynamic_variables: Record<string, string>;
}

type Phase = "idle" | "connecting" | "live" | "processing" | "error";

function VoiceInterview({ survey, respondent, onDone }: { survey: PublicSurvey; respondent: Record<string, string>; onDone: () => void }) {
  const conversation = useConversation();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const session = useRef<VoiceSession | null>(null);

  // After the call ends, the server receives the transcript via webhook and extracts answers.
  useEffect(() => {
    if (phase !== "processing" || !session.current) return;
    const { response_id, response_token } = session.current;
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const res = await api<{ status: string }>(`/public/responses/${response_id}`, { responseToken: response_token });
        if (["completed", "abandoned", "failed"].includes(res.status)) return onDone();
      } catch {
        /* keep polling */
      }
      if (attempts < 40) setTimeout(poll, 3000);
      else onDone();
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [phase, onDone]);

  async function start() {
    setPhase("connecting");
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      const data = await api<VoiceSession>(`/public/surveys/${survey.token}/responses`, {
        method: "POST",
        body: { channel: "voice", respondent },
      });
      session.current = data;
      conversation.startSession({
        signedUrl: data.signed_url,
        connectionType: "websocket",
        dynamicVariables: data.dynamic_variables,
        onConnect: () => setPhase("live"),
        onMessage: ({ message, role }) => setTurns((prev) => [...prev, { role: role === "agent" ? "agent" : "respondent", text: message }]),
        onDisconnect: () => setPhase((p) => (p === "error" ? p : "processing")),
        onError: (message) => {
          setError(message);
          setPhase("error");
        },
      });
    } catch (err) {
      setError(err instanceof DOMException ? "Microphone access is needed for a voice interview." : errorMessage(err));
      setPhase("error");
    }
  }

  const speaking = conversation.isSpeaking;

  return (
    <div className="glass-panel flex flex-col items-center rounded-2xl px-6 py-10 text-center">
      <div className="relative my-6 flex h-40 w-40 items-center justify-center">
        {phase === "live" && (
          <>
            <span className={cn("absolute inset-0 rounded-full brand-bg opacity-20", speaking && "animate-pulse-ring")} />
            <span className={cn("absolute inset-4 rounded-full brand-bg opacity-30", speaking && "animate-pulse-ring")} style={{ animationDelay: "400ms" }} />
          </>
        )}
        <span className="brand-bg relative flex h-24 w-24 items-center justify-center rounded-full shadow-2xl shadow-cyan-500/30">
          {phase === "connecting" || phase === "processing" ? (
            <Loader2 className="h-9 w-9 animate-spin text-white" />
          ) : phase === "live" ? (
            <div className="flex h-9 items-center gap-1">
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className={cn("w-1.5 origin-center rounded-full bg-white", speaking ? "h-9 animate-waveform" : "h-3")}
                  style={{ animationDelay: `${i * 120}ms` }}
                />
              ))}
            </div>
          ) : (
            <Mic className="h-9 w-9 text-white" />
          )}
        </span>
      </div>

      <h2 className="font-display text-xl font-semibold">
        {phase === "idle" && `Talk with ${survey.agent_name}`}
        {phase === "connecting" && "Connecting…"}
        {phase === "live" && (speaking ? `${survey.agent_name} is speaking` : "Listening…")}
        {phase === "processing" && "Saving your answers…"}
        {phase === "error" && "Couldn't start the call"}
      </h2>
      <p className="mt-2 max-w-sm text-sm text-ink-muted">
        {phase === "idle" && "A short spoken interview. Answer naturally. You can say “skip” for any question or “stop” to finish."}
        {phase === "live" && "Speak naturally. End the call any time."}
        {phase === "processing" && "This takes a few seconds while we turn the conversation into your responses."}
        {phase === "error" && error}
      </p>

      <div className="mt-8 flex gap-3">
        {(phase === "idle" || phase === "error") && (
          <Button size="lg" onClick={start}>
            <Mic /> {phase === "error" ? "Try again" : "Start interview"}
          </Button>
        )}
        {phase === "live" && (
          <>
            <Button size="lg" variant="secondary" onClick={() => conversation.setMuted(!conversation.isMuted)}>
              {conversation.isMuted ? <MicOff /> : <Mic />} {conversation.isMuted ? "Unmute" : "Mute"}
            </Button>
            <Button size="lg" variant="destructive" onClick={() => conversation.endSession()}>
              <PhoneOff /> End call
            </Button>
          </>
        )}
      </div>

      {turns.length > 0 && (
        <div className="mt-8 w-full max-w-lg space-y-2 text-left" aria-live="polite">
          {turns.slice(-4).map((t, i) => (
            <p key={i} className={cn("text-sm", t.role === "agent" ? "text-ink-muted" : "text-cyan-200")}>
              <span className="text-ink-faint">{t.role === "agent" ? survey.agent_name : "You"}: </span>
              {t.text}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function VoiceMode(props: { survey: PublicSurvey; respondent: Record<string, string>; onDone: () => void }) {
  return (
    <ConversationProvider>
      <VoiceInterview {...props} />
    </ConversationProvider>
  );
}
