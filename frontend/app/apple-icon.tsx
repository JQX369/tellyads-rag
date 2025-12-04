import { ImageResponse } from "next/og";

export const runtime = "edge";

export const size = {
  width: 180,
  height: 180,
};
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 100,
          background: "linear-gradient(135deg, #E63946 0%, #C62835 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "32px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              color: "#F8F9FA",
              fontWeight: "bold",
              fontFamily: "system-ui, sans-serif",
              fontSize: 70,
              letterSpacing: "-3px",
            }}
          >
            TA
          </span>
          <span
            style={{
              color: "rgba(248, 249, 250, 0.8)",
              fontWeight: "500",
              fontFamily: "monospace",
              fontSize: 16,
              letterSpacing: "4px",
              marginTop: -10,
            }}
          >
            TELLYADS
          </span>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
