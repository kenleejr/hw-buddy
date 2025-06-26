"use client";

import { cn } from "@/lib/utils"
import { Button } from "./button"

interface NavigationProps {
  currentPage?: "hw-buddy" | "parents"
}

export function Navigation({ currentPage = "hw-buddy" }: NavigationProps) {
  return (
    <nav className="w-full bg-white border-b border-border shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex space-x-8">
            <Button
              variant={currentPage === "hw-buddy" ? "default" : "ghost"}
              className={cn(
                "font-medium",
                currentPage === "hw-buddy" 
                  ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
                  : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
              )}
            >
              HW Buddy
            </Button>
            <Button
              variant={currentPage === "parents" ? "default" : "ghost"}
              className={cn(
                "font-medium",
                currentPage === "parents" 
                  ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
                  : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
              )}
            >
              Parents
            </Button>
          </div>
        </div>
      </div>
    </nav>
  )
}