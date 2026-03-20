import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
}

const variantStyles = {
  primary:
    "bg-accent text-black font-medium hover:bg-accent/90 active:bg-accent/80 shadow-[0_0_20px_-4px_rgba(0,212,255,0.3)] hover:shadow-[0_0_24px_-4px_rgba(0,212,255,0.4)]",
  danger:
    "bg-danger/10 text-danger border border-danger/20 hover:bg-danger/20 hover:border-danger/30",
  ghost:
    "bg-transparent text-text-muted hover:text-text-primary hover:bg-white/[0.04]",
  outline:
    "border border-border text-text-primary hover:bg-surface hover:border-white/[0.1]",
};

const sizeStyles = {
  sm: "h-8 text-xs px-3 rounded-lg",
  md: "h-10 text-sm px-4 rounded-lg",
  lg: "h-12 text-base px-6 rounded-xl",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "primary", size = "md", disabled, ...props },
    ref
  ) => (
    <button
      ref={ref}
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 cursor-pointer select-none",
        "disabled:opacity-50 disabled:pointer-events-none",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { Button };
