import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--uq-purple)] text-white hover:bg-[var(--uq-purple-dark)] focus-visible:outline-[var(--focus-ring)]",
        secondary:
          "border border-[var(--border-light)] bg-white text-[var(--uq-purple)] hover:bg-[var(--uq-purple-light)]",
        ghost:
          "text-[var(--uq-purple)] hover:bg-[var(--uq-purple-light)]",
        warning:
          "bg-[var(--uq-gold)] text-[var(--text-primary)] hover:bg-[#e4a700]",
        subtle:
          "bg-[var(--uq-purple-light)] text-[var(--uq-purple-dark)] hover:bg-[#e2d4ef]",
      },
      size: {
        default: "h-11 px-5",
        sm: "h-9 px-3",
        lg: "h-12 px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}
