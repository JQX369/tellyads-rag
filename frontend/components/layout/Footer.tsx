import Link from "next/link";
import { AtomicStarburst } from "@/components/ui/Starburst";

// Social Icons
function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function FacebookIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  );
}

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="relative bg-void border-t border-white/5">
      {/* Decorative element */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <AtomicStarburst size={40} color="#E63946" />
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
          {/* Brand column */}
          <div className="md:col-span-2">
            <Link href="/" className="inline-block mb-4">
              <div className="flex items-center gap-3">
                <div className="relative w-10 h-10 flex items-center justify-center">
                  <div className="absolute inset-0 bg-transmission rounded-sm" />
                  <span className="relative font-display text-base font-bold text-signal tracking-tighter">
                    TA
                  </span>
                </div>
                <span className="font-display text-xl font-bold text-signal">
                  TellyAds
                </span>
              </div>
            </Link>
            <p className="font-mono text-sm text-antenna max-w-xs leading-relaxed mb-6">
              The definitive archive of television advertising.
              Preserving commercial culture since the golden age of TV.
            </p>

            {/* Social Links */}
            <div className="flex items-center gap-4">
              <a
                href="https://x.com/tellyads"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 flex items-center justify-center rounded-full bg-white/5 hover:bg-transmission/20 transition-colors group"
                aria-label="Follow us on X (Twitter)"
              >
                <XIcon className="w-5 h-5 text-antenna group-hover:text-signal transition-colors" />
              </a>
              <a
                href="https://facebook.com/tellyads"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 flex items-center justify-center rounded-full bg-white/5 hover:bg-transmission/20 transition-colors group"
                aria-label="Follow us on Facebook"
              >
                <FacebookIcon className="w-5 h-5 text-antenna group-hover:text-signal transition-colors" />
              </a>
            </div>
          </div>

          {/* Browse column */}
          <div>
            <h4 className="font-mono text-label uppercase tracking-ultra-wide text-transmission mb-4">
              Browse
            </h4>
            <nav className="flex flex-col gap-2">
              <FooterLink href="/browse">All Ads</FooterLink>
              <FooterLink href="/brands">Brands</FooterLink>
              <FooterLink href="/categories">Categories</FooterLink>
              <FooterLink href="/random">Random</FooterLink>
            </nav>
          </div>

          {/* Info column */}
          <div>
            <h4 className="font-mono text-label uppercase tracking-ultra-wide text-transmission mb-4">
              Info
            </h4>
            <nav className="flex flex-col gap-2">
              <FooterLink href="/about">About</FooterLink>
              <FooterLink href="/latest">Latest Ads</FooterLink>
              <FooterLink href="/search">Search</FooterLink>
            </nav>
          </div>
        </div>

        {/* Partners Section */}
        <div className="mt-12 pt-8 border-t border-white/5">
          <div className="flex flex-col md:flex-row items-center justify-center gap-6 md:gap-10">
            <a
              href="https://guerillascope.co.uk"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 group"
            >
              <span className="font-mono text-[10px] uppercase tracking-widest text-antenna">
                Powered by
              </span>
              <span className="font-display font-bold text-signal group-hover:text-transmission transition-colors">
                Guerillascope
              </span>
            </a>
            <div className="hidden md:block w-px h-4 bg-white/10" />
            <a
              href="https://custom-stories.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 group"
            >
              <span className="font-mono text-[10px] uppercase tracking-widest text-antenna">
                Creative Partner
              </span>
              <span className="font-display font-bold text-signal group-hover:text-transmission transition-colors">
                Custom Stories
              </span>
            </a>
            <div className="hidden md:block w-px h-4 bg-white/10" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-antenna">
                Leverage our Database
              </span>
              <span className="font-display font-bold text-transmission">
                OneShot
              </span>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-16 pt-8 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="font-mono text-xs text-antenna">
            &copy; {currentYear} TellyAds. All rights reserved.
          </p>

          <div className="flex items-center gap-6">
            <span className="font-mono text-xs text-antenna">
              Built for the love of advertising
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="font-mono text-sm text-antenna hover:text-signal transition-colors"
    >
      {children}
    </Link>
  );
}
