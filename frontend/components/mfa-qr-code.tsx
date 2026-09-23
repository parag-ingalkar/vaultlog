"use client";

import { QRCodeSVG } from "qrcode.react";

export function MfaQrCode({ uri }: { uri: string }) {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="rounded-[var(--radius-panel)] border border-border bg-white p-4">
        <QRCodeSVG
          value={uri}
          size={180}
          level="M"
          includeMargin={false}
          aria-label="QR code for authenticator app"
        />
      </div>
      <p className="text-center text-xs text-muted">
        Scan with your authenticator app, or enter the setup key manually if
        needed.
      </p>
      <details className="w-full text-xs text-muted">
        <summary className="cursor-pointer select-none text-center text-primary">
          Show setup key
        </summary>
        <p className="mt-2 break-all rounded-[var(--radius-control)] bg-surface-2 p-3 font-mono text-ink">
          {uri}
        </p>
      </details>
    </div>
  );
}
