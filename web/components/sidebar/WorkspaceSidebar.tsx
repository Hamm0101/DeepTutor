"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { SidebarShell } from "@/components/sidebar/SidebarShell";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { AdminLink } from "@/components/auth/AdminLink";
import { ProfileLink } from "@/components/auth/ProfileLink";
import { useUnifiedChat } from "@/context/UnifiedChatContext";
import {
  deleteSession,
  listSessions,
  updateSessionTitle,
  type SessionSummary,
} from "@/lib/session-api";

export default function WorkspaceSidebar() {
  const { t } = useTranslation();
  const router = useRouter();
  const {
    newSession,
    cancelStreamingTurn,
    selectedSessionId,
    sessionStatuses,
    sidebarRefreshToken,
  } = useUnifiedChat();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const hasLoadedSessionsRef = useRef(false);
  // Debounce rapid sidebar refresh triggers (STREAM_END + SET_SESSION_TITLE
  // fire back-to-back each turn). Without this, ``force: true`` bypasses the
  // 15s client cache and hits the server twice per turn. A 2s debounce lets
  // both signals coalesce into one cache-bypassing fetch, and the TTL cache
  // handles intermediate refresh-token bumps silently.
  const pendingRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshSessions = useCallback(async () => {
    if (!hasLoadedSessionsRef.current) {
      setLoadingSessions(true);
    }
    try {
      setSessions(await listSessions(50, 0, {}));
      hasLoadedSessionsRef.current = true;
    } catch (error) {
      console.error("Failed to load sessions", error);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  // First mount shows the skeleton; subsequent refreshes triggered by
  // ``sidebarRefreshToken`` (STREAM_END, server-side session bind,
  // turn deletion) silently swap in the new list. The token can fire
  // multiple times in quick succession (e.g. STREAM_END immediately
  // followed by SET_SESSION_TITLE), so we debounce to avoid duplicate
  // fetches. The 15s TTL inside ``listSessions`` handles the common case
  // where the list hasn't actually changed.
  useEffect(() => {
    // First load is immediate; subsequent triggers go through the debounce.
    if (!hasLoadedSessionsRef.current) {
      void refreshSessions();
      return;
    }
    if (pendingRefreshRef.current) {
      clearTimeout(pendingRefreshRef.current);
    }
    pendingRefreshRef.current = setTimeout(() => {
      pendingRefreshRef.current = null;
      void refreshSessions();
    }, 2000);
    return () => {
      if (pendingRefreshRef.current) {
        clearTimeout(pendingRefreshRef.current);
        pendingRefreshRef.current = null;
      }
    };
  }, [refreshSessions, sidebarRefreshToken]);

  const orderedSessions = sessions
    .map((session, index) => {
      const runtime = sessionStatuses[session.session_id];
      return {
        index,
        session: runtime
          ? {
              ...session,
              status: runtime.status,
              active_turn_id: runtime.activeTurnId || session.active_turn_id,
            }
          : session,
      };
    })
    .sort((a, b) => {
      const aPriority = a.session.status === "running" ? 0 : 1;
      const bPriority = b.session.status === "running" ? 0 : 1;
      if (aPriority !== bPriority) return aPriority - bPriority;
      return a.index - b.index;
    })
    .map(({ session }) => session);

  // Cancel any in-flight streaming turn before starting a fresh session, so a
  // new chat never inherits a still-running turn (mirrors handleDeleteSession).
  const handleNewChat = useCallback(() => {
    cancelStreamingTurn();
    newSession();
    router.push("/home");
  }, [cancelStreamingTurn, newSession, router]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      router.push(`/home/${sessionId}`);
    },
    [router],
  );

  const handleRenameSession = useCallback(
    async (sessionId: string, title: string) => {
      const updated = await updateSessionTitle(sessionId, title);
      setSessions((prev) =>
        prev.map((session) =>
          session.session_id === sessionId
            ? {
                ...session,
                title: updated.title,
                updated_at: updated.updated_at,
              }
            : session,
        ),
      );
    },
    [],
  );

  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      if (!window.confirm(t("Delete this chat history?"))) return;
      await deleteSession(sessionId);
      setSessions((prev) =>
        prev.filter((session) => session.session_id !== sessionId),
      );
      if (selectedSessionId === sessionId) {
        cancelStreamingTurn();
        newSession();
        router.push("/home");
      }
    },
    [cancelStreamingTurn, newSession, router, selectedSessionId, t],
  );

  return (
    <SidebarShell
      showSessions
      sessions={orderedSessions}
      activeSessionId={selectedSessionId}
      loadingSessions={loadingSessions}
      onNewChat={handleNewChat}
      onSelectSession={handleSelectSession}
      onRenameSession={handleRenameSession}
      onDeleteSession={handleDeleteSession}
      footerSlot={(collapsed) => (
        <>
          <ProfileLink collapsed={collapsed} />
          <AdminLink collapsed={collapsed} />
          <LogoutButton collapsed={collapsed} />
        </>
      )}
    />
  );
}
