"use client";

import { forwardRef, useRef, MouseEvent, ReactNode } from "react";
import { clsx } from "clsx";
import Link from "next/link";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  href?: string;
  magnetic?: boolean;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
  (
    {
      children,
      variant = "primary",
      size = "md",
      href,
      magnetic = true,
      className,
      onClick,
      disabled = false,
      type = "button",
    },
    ref
  ) => {
    const buttonRef = useRef<HTMLButtonElement | HTMLAnchorElement>(null);
    const innerRef = useRef<HTMLSpanElement>(null);

    const handleMouseMove = (e: MouseEvent) => {
      if (!magnetic || !buttonRef.current || !innerRef.current) return;

      const rect = buttonRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;

      // Subtle magnetic pull
      buttonRef.current.style.transform = `translate(${x * 0.1}px, ${y * 0.1}px)`;
      innerRef.current.style.transform = `translate(${x * 0.05}px, ${y * 0.05}px)`;
    };

    const handleMouseLeave = () => {
      if (!magnetic || !buttonRef.current || !innerRef.current) return;
      buttonRef.current.style.transform = "translate(0, 0)";
      innerRef.current.style.transform = "translate(0, 0)";
    };

    const baseStyles = clsx(
      "relative inline-flex items-center justify-center font-mono uppercase tracking-ultra-wide",
      "transition-all duration-300 ease-expo-out",
      "disabled:opacity-50 disabled:cursor-not-allowed",
      magnetic && "btn-magnetic"
    );

    const variants = {
      primary: clsx(
        "bg-transmission text-signal border-2 border-transmission",
        "hover:bg-transmission-dark hover:border-transmission-dark",
        "active:scale-95"
      ),
      secondary: clsx(
        "bg-static text-signal border-2 border-static",
        "hover:bg-antenna hover:border-antenna",
        "active:scale-95"
      ),
      ghost: clsx(
        "bg-transparent text-signal",
        "hover:text-transmission",
        "active:scale-95"
      ),
      outline: clsx(
        "bg-transparent text-signal border-2 border-signal/20",
        "hover:border-transmission hover:text-transmission",
        "active:scale-95"
      ),
    };

    const sizes = {
      sm: "px-4 py-2 text-xs",
      md: "px-6 py-3 text-sm",
      lg: "px-8 py-4 text-base",
    };

    const combinedClassName = clsx(
      baseStyles,
      variants[variant],
      sizes[size],
      "rounded-pill",
      className
    );

    const content = (
      <span ref={innerRef} className="btn-magnetic-inner flex items-center gap-2">
        {children}
      </span>
    );

    if (href) {
      return (
        <Link
          href={href}
          ref={ref as React.Ref<HTMLAnchorElement>}
          className={combinedClassName}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {content}
        </Link>
      );
    }

    return (
      <button
        ref={(node) => {
          (buttonRef as React.MutableRefObject<HTMLButtonElement | null>).current = node;
          if (typeof ref === "function") ref(node);
          else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
        }}
        type={type}
        className={combinedClassName}
        onClick={onClick}
        disabled={disabled}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {content}
      </button>
    );
  }
);

Button.displayName = "Button";
