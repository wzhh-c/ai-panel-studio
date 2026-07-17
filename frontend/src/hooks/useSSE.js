import { useEffect, useRef } from 'react';

/**
 * Subscribe to the SSE event stream for a discussion.
 *
 * @param {string|null} discussionId  — discussion ID (null = don't connect)
 * @param {function}    onEvent       — callback(eventType, data) for each event
 */
export default function useSSE(discussionId, onEvent) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!discussionId) return;

    const base = 'http://127.0.0.1:8080/api';
    const url = `${base}/discussions/${discussionId}/stream`;
    const es = new EventSource(url);

    const events = [
      'speech',
      'status_update',
      'consensus_update',
      'divergence_update',
      'summary',
    ];

    events.forEach((type) => {
      es.addEventListener(type, (e) => {
        try {
          const envelope = JSON.parse(e.data);
          onEventRef.current(type, envelope.data ?? envelope);
        } catch {
          // ignore parse errors on keep-alive comments
        }
      });
    });

    // Generic handler for unlabelled messages.
    es.onmessage = (e) => {
      try {
        const envelope = JSON.parse(e.data);
        onEventRef.current(envelope.event ?? 'message', envelope.data ?? envelope);
      } catch {
        /* keep-alive */
      }
    };

    es.onerror = () => {
      // EventSource will auto-reconnect; do nothing here.
    };

    return () => es.close();
  }, [discussionId]);
}
