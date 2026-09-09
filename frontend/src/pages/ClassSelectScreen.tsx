import React from 'react';

interface ClassSelectScreenProps {
  selectedClass: number | null;
  onSelectClass: (c: number) => void;
  onBack: () => void;
  onHome: () => void;
}

export const ClassSelectScreen: React.FC<ClassSelectScreenProps> = ({
  selectedClass,
  onSelectClass,
}) => {
  const levels = [
    { num: 1, name: 'Algebra I', category: 'math', bg: 'bg-[#e2241f] text-white' },
    { num: 2, name: 'Geometry', category: 'math', bg: 'bg-[#e2241f] text-white' },
    { num: 3, name: 'Calculus', category: 'math', bg: 'bg-[#e2241f] text-white' },
    { num: 4, name: 'Biology', category: 'science', bg: 'bg-[#fecb00] text-[#6e5700]' },
    { num: 5, name: 'Physics', category: 'science', bg: 'bg-[#fecb00] text-[#6e5700]' },
    { num: 6, name: 'Chemistry', category: 'science', bg: 'bg-[#fecb00] text-[#6e5700]' },
    { num: 7, name: 'World Hist', category: 'history', bg: 'bg-[#72fe88] text-[#002107]' },
    { num: 8, name: 'Euro Hist', category: 'history', bg: 'bg-[#72fe88] text-[#002107]' },
    { num: 9, name: 'US Hist', category: 'history', bg: 'bg-[#72fe88] text-[#002107]' },
    { num: 10, name: 'Art & CS', category: 'electives', bg: 'bg-[#e5e2e1] text-[#1c1b1b]' },
  ];

  return (
    <div className="flex-1 flex flex-col justify-center items-center px-6 pt-16 pb-24 w-full h-full max-w-6xl mx-auto overflow-y-auto">
      {/* Title Badge Header */}
      <div className="text-center mb-6">
        <h2 className="font-headline text-3xl md:text-4xl font-black text-[#bc000a] bg-[#ffffff] inline-block px-8 py-3.5 pixel-border brutal-shadow uppercase">
          Choose Your Class (1 to 10)
        </h2>
        <br />
        <p className="font-pixel text-xs font-bold text-[#5d3f3b] mt-3 bg-[#ffffff] inline-block px-4 py-1.5 border-2 border-[#1c1b1b] brutal-shadow uppercase">
          TAP A GRADE LEVEL TO BEGIN LESSON MODULE
        </p>
      </div>

      {/* 10 Grade Cartridges Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 w-full max-w-5xl">
        {levels.map((lvl) => {
          const isSelected = selectedClass !== null && selectedClass === lvl.num;
          return (
            <button
              key={lvl.num}
              onClick={() => onSelectClass(lvl.num)}
              className={`aspect-square ${lvl.bg} pixel-border brutal-shadow brutal-button-active flex flex-col items-center justify-center p-4 relative group overflow-hidden cursor-pointer transition-all ${
                isSelected ? 'ring-4 ring-[#1c1b1b] scale-105' : ''
              }`}
            >
              <span className="font-headline font-black text-5xl mb-1">
                {lvl.num < 10 ? `0${lvl.num}` : lvl.num}
              </span>
              <span className="font-pixel text-xs font-bold uppercase text-center">
                CLASS {lvl.num}
              </span>

              {/* Selected Badge */}
              {isSelected && (
                <div className="absolute top-2 right-2 bg-[#1c1b1b] text-white px-2 py-0.5 font-pixel text-[10px] font-bold">
                  ACTIVE
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
