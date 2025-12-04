import { ImageResponse } from "next/og";

export const runtime = "edge";

export const size = {
  width: 32,
  height: 32,
};
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 14,
          background: "#E63946",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "4px",
        }}
      >
        <span
          style={{
            color: "#F8F9FA",
            fontWeight: "bold",
            fontFamily: "system-ui, sans-serif",
            letterSpacing: "-1px",
          }}
        >
          TA
        </span>
      </div>
    ),
    {
      ...size,
    }
  );
}
