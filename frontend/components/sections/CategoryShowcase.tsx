"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { clsx } from "clsx";

interface Category {
  id: string;
  name: string;
  icon: string;
  count?: number;
}

const categories: Category[] = [
  { id: "automotive", name: "Automotive", icon: "🚗" },
  { id: "fmcg", name: "FMCG", icon: "🛒" },
  { id: "finance", name: "Finance", icon: "💳" },
  { id: "tech", name: "Technology", icon: "💻" },
  { id: "retail", name: "Retail", icon: "🏪" },
  { id: "entertainment", name: "Entertainment", icon: "🎬" },
  { id: "telecom", name: "Telecom", icon: "📱" },
  { id: "travel", name: "Travel", icon: "✈️" },
  { id: "pharma", name: "Pharma", icon: "💊" },
  { id: "alcohol", name: "Alcohol", icon: "🍺" },
  { id: "charity", name: "Charity", icon: "❤️" },
  { id: "government", name: "Government", icon: "🏛️" },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.5,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  },
};

export function CategoryShowcase() {
  return (
    <section className="relative py-24 bg-static/30">
      {/* Section header */}
      <div className="max-w-7xl mx-auto px-6 lg:px-12 mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-flex items-center gap-3 mb-4">
            <span className="w-8 h-px bg-transmission" />
            <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
              Categories
            </span>
          </span>
          <h2 className="font-display text-display-md font-bold text-signal">
            What&apos;s Playing
          </h2>
        </motion.div>
      </div>

      {/* Category grid */}
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <motion.div
          className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {categories.map((category) => (
            <motion.div key={category.id} variants={itemVariants}>
              <CategoryCard category={category} />
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* View all link */}
      <div className="max-w-7xl mx-auto px-6 lg:px-12 mt-12 text-center">
        <Link
          href="/categories"
          className="font-mono text-sm text-antenna hover:text-transmission transition-colors link-underline"
        >
          View all categories →
        </Link>
      </div>
    </section>
  );
}

function CategoryCard({ category }: { category: Category }) {
  return (
    <Link href={`/browse?category=${category.id}`}>
      <div
        className={clsx(
          "group relative p-4 aspect-square",
          "bg-void/50 backdrop-blur-sm",
          "border border-white/5 rounded",
          "flex flex-col items-center justify-center gap-3",
          "transition-all duration-300 ease-expo-out",
          "hover:border-transmission/30 hover:bg-transmission/5",
          "hover:-translate-y-1"
        )}
      >
        {/* Icon */}
        <span className="text-3xl grayscale group-hover:grayscale-0 transition-all duration-300">
          {category.icon}
        </span>

        {/* Name */}
        <span className="font-mono text-xs uppercase tracking-ultra-wide text-antenna group-hover:text-signal transition-colors text-center">
          {category.name}
        </span>

        {/* Corner accent */}
        <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-transmission/0 group-hover:border-transmission/50 transition-colors" />
        <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-transmission/0 group-hover:border-transmission/50 transition-colors" />
      </div>
    </Link>
  );
}
