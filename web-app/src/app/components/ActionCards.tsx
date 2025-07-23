"use client";

interface ActionCardsProps {
  onCardClick?: (action: string) => void;
}

export function ActionCards({ onCardClick }: ActionCardsProps) {
  const cards = [
    {
      id: 'hint',
      title: 'Ask me for a hint!',
      icon: '💡',
      description: 'Get step-by-step guidance',
      gradient: 'from-blue-500 to-blue-600',
      hoverGradient: 'from-blue-600 to-blue-700'
    },
    {
      id: 'visualization',
      title: 'Ask me for a visualization!',
      icon: '📊',
      description: 'See interactive charts and graphs',
      gradient: 'from-green-500 to-green-600',
      hoverGradient: 'from-green-600 to-green-700'
    },
    {
      id: 'search',
      title: 'Search the internet or my textbook!',
      icon: '🔍',
      description: 'Find related resources',
      gradient: 'from-purple-500 to-purple-600',
      hoverGradient: 'from-purple-600 to-purple-700'
    }
  ];

  return (
    <div className="flex justify-center items-center min-h-[200px] p-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
        {cards.map((card) => (
          <div
            key={card.id}
            onClick={() => onCardClick?.(card.id)}
            className={`
              relative overflow-hidden rounded-2xl cursor-pointer
              transform transition-all duration-300 ease-out
              hover:scale-105 hover:shadow-xl
              bg-gradient-to-br ${card.gradient}
              group
            `}
          >
            {/* Hover effect overlay */}
            <div className={`
              absolute inset-0 bg-gradient-to-br ${card.hoverGradient}
              opacity-0 group-hover:opacity-100 transition-opacity duration-300
            `} />
            
            {/* Content */}
            <div className="relative p-6 text-white">
              <div className="text-3xl mb-3">{card.icon}</div>
              <h3 className="font-bold text-lg mb-2 leading-tight">
                {card.title}
              </h3>
              <p className="text-sm opacity-90">
                {card.description}
              </p>
            </div>

            {/* Bottom accent line */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20" />
          </div>
        ))}
      </div>
    </div>
  );
}