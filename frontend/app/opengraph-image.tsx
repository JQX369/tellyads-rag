import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "TellyAds - Britain's TV Ad Archive";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)",
          position: "relative",
        }}
      >
        {/* Decorative circles */}
        <div
          style={{
            position: "absolute",
            top: -100,
            left: -100,
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "rgba(230, 57, 70, 0.15)",
            filter: "blur(60px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: -100,
            right: -100,
            width: 500,
            height: 500,
            borderRadius: "50%",
            background: "rgba(230, 57, 70, 0.1)",
            filter: "blur(80px)",
          }}
        />

        {/* Main content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 24,
          }}
        >
          {/* Logo */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                background: "#E63946",
                borderRadius: 12,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span
                style={{
                  fontSize: 48,
                  fontWeight: "bold",
                  color: "#F8F9FA",
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                T
              </span>
            </div>
            <span
              style={{
                fontSize: 64,
                fontWeight: "bold",
                color: "#F8F9FA",
                fontFamily: "system-ui, sans-serif",
              }}
            >
              TellyAds
            </span>
          </div>

          {/* Tagline */}
          <div
            style={{
              fontSize: 32,
              color: "#E63946",
              fontFamily: "system-ui, sans-serif",
              fontWeight: 600,
            }}
          >
            Britain&apos;s TV Ad Archive
          </div>

          {/* Description */}
          <div
            style={{
              fontSize: 20,
              color: "#6B6B6B",
              fontFamily: "monospace",
              maxWidth: 600,
              textAlign: "center",
            }}
          >
            Explore thousands of UK television commercials from 2000 to today
          </div>

          {/* Stats */}
          <div
            style={{
              display: "flex",
              gap: 60,
              marginTop: 20,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <span style={{ fontSize: 40, fontWeight: "bold", color: "#F8F9FA" }}>20K+</span>
              <span style={{ fontSize: 14, color: "#6B6B6B", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 2 }}>
                Adverts
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <span style={{ fontSize: 40, fontWeight: "bold", color: "#F8F9FA" }}>3000+</span>
              <span style={{ fontSize: 14, color: "#6B6B6B", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 2 }}>
                Brands
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <span style={{ fontSize: 40, fontWeight: "bold", color: "#F8F9FA" }}>24yrs</span>
              <span style={{ fontSize: 14, color: "#6B6B6B", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 2 }}>
                Of Ads
              </span>
            </div>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
