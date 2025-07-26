"use client";

import { cn } from "@/lib/utils"
import { Button } from "./button"

interface NavigationProps {
  currentPage?: "hw-buddy" | "parents"
}

export function Navigation({ 
  currentPage = "hw-buddy"
}: NavigationProps) {

  return (
    <div className="flex items-center justify-between w-full px-4 py-3 bg-white border-b border-gray-200">
      {/* Compact Left Navigation Buttons */}
      <div className="flex gap-3">
        <Button
          variant={currentPage === "hw-buddy" ? "default" : "outline"}
          size="sm"
          className={cn(
            "font-medium px-3 py-1 text-sm h-8",
            currentPage === "hw-buddy" 
              ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
              : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
          )}
        >
          HW Buddy
        </Button>
        <Button
          variant={currentPage === "parents" ? "default" : "outline"}
          size="sm"
          className={cn(
            "font-medium px-3 py-1 text-sm h-8",
            currentPage === "parents" 
              ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
              : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
          )}
        >
          Parents
        </Button>
      </div>

      {/* Right side - empty for now, session status moved to agent column */}
      <div></div>
    </div>
  )
}