import { useCallback, useEffect, useRef } from "react";

export default function StitchIframe({ html, title, className = "", onBind, allow = "" }) {
  const iframeRef = useRef(null);
  const cleanupRef = useRef(null);

  const bind = useCallback(() => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }

    if (!onBind || !iframeRef.current?.contentDocument) {
      return;
    }

    const maybeCleanup = onBind(iframeRef.current.contentDocument, iframeRef.current);
    if (typeof maybeCleanup === "function") {
      cleanupRef.current = maybeCleanup;
    }
  }, [onBind]);

  useEffect(() => {
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, []);

  return (
    <iframe
      ref={iframeRef}
      title={title}
      srcDoc={html}
      className={`h-full w-full border-0 ${className}`}
      allow={allow}
      onLoad={bind}
    />
  );
}
