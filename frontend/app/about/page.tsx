import { Metadata } from "next";
import Link from "next/link";
import { Header, Footer } from "@/components/layout";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "About TellyAds | Our Heritage",
  description:
    "Founded in 2006, TellyAds is the UK's largest archive of television commercials. Learn about our heritage and mission to preserve advertising history.",
});

const timelineEvents = [
  {
    year: "2006",
    title: "Founded",
    description: "Founded by Jon Cousins and Caroline Ashcroft",
    color: "#E63946",
  },
  {
    year: "2012",
    title: "New Guardians",
    description: "Continued by Guerillascope",
    color: "#3B82F6",
  },
  {
    year: "2020",
    title: "Major Milestone",
    description: "Reached 20,000 Ads Listed",
    color: "#10B981",
  },
  {
    year: "2023",
    title: "New Era",
    description: "Revamped & Relaunched",
    color: "#F59E0B",
  },
];

export default function AboutPage() {
  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        {/* Hero Section */}
        <section className="relative py-20 overflow-hidden">
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-0 w-full h-2 bg-transmission" />
          </div>

          <div className="max-w-7xl mx-auto px-6 lg:px-12">
            <div className="grid lg:grid-cols-2 gap-16 items-center">
              {/* Left: Title */}
              <div>
                <h1 className="font-display text-display-lg md:text-[80px] font-bold text-signal leading-none">
                  Our
                  <br />
                  Heritage
                </h1>
                <p className="font-mono text-lg text-antenna mt-6">
                  2006–Present
                </p>
              </div>

              {/* Right: Timeline */}
              <div className="space-y-8">
                {timelineEvents.map((event, index) => (
                  <TimelineItem key={event.year} event={event} index={index} />
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Mission Section */}
        <section className="py-24 bg-static/20">
          <div className="max-w-4xl mx-auto px-6 lg:px-12 text-center">
            <span className="inline-flex items-center gap-3 mb-6">
              <span className="w-12 h-px bg-transmission" />
              <span className="font-mono text-xs uppercase tracking-widest text-transmission">
                Our Mission
              </span>
              <span className="w-12 h-px bg-transmission" />
            </span>

            <h2 className="font-display text-3xl md:text-4xl font-bold text-signal mb-8">
              Preserving Britain&apos;s Advertising Heritage
            </h2>

            <p className="font-mono text-antenna leading-relaxed mb-6">
              TellyAds is the UK&apos;s most comprehensive archive of television
              commercials. We believe that advertising is a mirror of culture,
              capturing the zeitgeist of each era in 30-second snapshots.
            </p>

            <p className="font-mono text-antenna leading-relaxed">
              From the iconic campaigns of the millennium to the streaming era,
              we preserve and celebrate the creativity, storytelling, and
              cultural impact of British television advertising.
            </p>
          </div>
        </section>

        {/* Partners Section */}
        <section className="py-24">
          <div className="max-w-7xl mx-auto px-6 lg:px-12">
            <div className="text-center mb-16">
              <span className="inline-flex items-center gap-3 mb-6">
                <span className="w-12 h-px bg-transmission" />
                <span className="font-mono text-xs uppercase tracking-widest text-transmission">
                  Our Partners
                </span>
                <span className="w-12 h-px bg-transmission" />
              </span>

              <h2 className="font-display text-3xl md:text-4xl font-bold text-signal">
                Powered by Industry Leaders
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <PartnerCard
                name="Guerillascope"
                role="Powered by"
                description="Leading the future of TV advertising intelligence and media planning."
                color="#E63946"
              />
              <PartnerCard
                name="Customstories"
                role="Creative Partner"
                description="Crafting compelling narratives and creative solutions for brands."
                color="#3B82F6"
              />
              <PartnerCard
                name="OneShot"
                role="Leverage our Database"
                description="Transform advertising insights into actionable intelligence."
                color="#10B981"
              />
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 bg-static/20">
          <div className="max-w-4xl mx-auto px-6 lg:px-12 text-center">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-signal mb-6">
              Ready to Explore?
            </h2>
            <p className="font-mono text-antenna mb-10">
              Dive into decades of advertising history and discover the ads that
              shaped British culture.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/browse"
                className="inline-flex items-center justify-center px-8 py-4 font-mono uppercase tracking-ultra-wide text-sm bg-transmission text-signal rounded-pill hover:bg-transmission-dark transition-colors"
              >
                Browse the Archive
              </Link>
              <Link
                href="/latest"
                className="inline-flex items-center justify-center px-8 py-4 font-mono uppercase tracking-ultra-wide text-sm bg-transparent text-signal border-2 border-white/20 rounded-pill hover:border-transmission hover:text-transmission transition-colors"
              >
                Latest Ads
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

function TimelineItem({
  event,
  index,
}: {
  event: {
    year: string;
    title: string;
    description: string;
    color: string;
  };
  index: number;
}) {
  return (
    <div className="flex items-start gap-6 group">
      {/* Year badge */}
      <div
        className="flex-shrink-0 w-16 h-16 rounded-lg flex items-center justify-center font-display text-xl font-bold text-signal transition-transform group-hover:scale-105"
        style={{ backgroundColor: `${event.color}20`, borderColor: event.color }}
      >
        {event.year.slice(2)}
      </div>

      {/* Content */}
      <div className="pt-2">
        <h3
          className="font-display text-xl font-semibold mb-1"
          style={{ color: event.color }}
        >
          {event.description}
        </h3>
        <p className="font-mono text-sm text-antenna">{event.title}</p>
      </div>
    </div>
  );
}

function PartnerCard({
  name,
  role,
  description,
  color,
}: {
  name: string;
  role: string;
  description: string;
  color: string;
}) {
  return (
    <div className="group relative bg-static/30 border border-white/5 rounded-xl p-8 transition-all hover:border-white/10 hover:-translate-y-1">
      {/* Top accent */}
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-xl"
        style={{ backgroundColor: color }}
      />

      {/* Role label */}
      <span
        className="inline-block font-mono text-[10px] uppercase tracking-widest px-2 py-1 rounded-sm mb-4"
        style={{ backgroundColor: `${color}20`, color }}
      >
        {role}
      </span>

      {/* Name */}
      <h3 className="font-display text-2xl font-bold text-signal mb-3">
        {name}
      </h3>

      {/* Description */}
      <p className="font-mono text-sm text-antenna leading-relaxed">
        {description}
      </p>
    </div>
  );
}
