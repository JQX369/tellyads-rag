import { clsx } from "clsx";
import { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "outline" | "transmission" | "muted";
  size?: "sm" | "md";
  className?: string;
  onClick?: () => void;
}

export function Badge({
  children,
  variant = "default",
  size = "sm",
  className,
  onClick,
}: BadgeProps) {
  const variants = {
    default: "bg-static text-signal border-white/10",
    outline: "bg-transparent text-signal border-white/20",
    transmission: "bg-transmission/10 text-transmission border-transmission/30",
    muted: "bg-static/50 text-antenna border-white/5",
  };

  const sizes = {
    sm: "px-2 py-0.5 text-[10px]",
    md: "px-3 py-1 text-xs",
  };

  const Component = onClick ? "button" : "span";

  return (
    <Component
      onClick={onClick}
      className={clsx(
        "inline-flex items-center font-mono uppercase tracking-ultra-wide border rounded-sm",
        variants[variant],
        sizes[size],
        onClick && "cursor-pointer hover:opacity-80 transition-opacity",
        className
      )}
    >
      {children}
    </Component>
  );
}
