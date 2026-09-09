import React, { useState, useEffect } from 'react';
import type { Chapter } from '../api/client';
import { fetchChapters } from '../api/client';

interface ClassSelectProps {
  selectedClass: number;
  setSelectedClass: (c: number) => void;
  selectedSubject: string;
  setSelectedSubject: (s: string) => void;
  onSelectChapter: (ch: Chapter) => void;
}

export const ClassSelect: React.FC<ClassSelectProps> = ({
  selectedClass,
  setSelectedClass,
  selectedSubject,
  setSelectedSubject,
  onSelectChapter,
}) => {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchChapters(selectedClass, selectedSubject).then((list) => {
      setChapters(list || []);
      setLoading(false);
    });
  }, [selectedClass, selectedSubject]);

  const classes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const subjects = [
    { id: 'Science', label: 'SCIENCE', icon: 'science', bg: 'bg-[#72fe88] text-[#002107]' },
    { id: 'Mathematics', label: 'MATHS', icon: 'calculate', bg: 'bg-[#fecb00] text-[#6e5700]' },
    { id: 'Social Science', label: 'SOCIAL SCIENCE', icon: 'public', bg: 'bg-[#ffdad5] text-[#930005]' },
  ];

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-8">
      {/* Kiosk Section Header */}
      <div className="bg-[#ffffff] pixel-border p-6 pixel-corners hard-shadow">
        <span className="font-pixel text-xs font-bold text-[#bc000a] uppercase bg-[#ffdad5] px-2.5 py-1 border border-[#1c1b1b]">
          ROBO-LEARN CURRICULUM SELECTOR
        </span>
        <h1 className="font-headline font-bold text-3xl text-[#1c1b1b] mt-2">
          Select Grade & Subject Cartridge
        </h1>
        <p className="font-body text-sm text-[#5d3f3b]">
          Tap a grade tile (Class 1–10) and subject cartridge to view available NCERT textbook chapters.
        </p>
      </div>

      {/* Grade Selector (Class 1–10 Touch Cartridges) */}
      <div className="space-y-3">
        <h2 className="font-pixel text-xs font-bold text-[#1c1b1b] uppercase flex items-center gap-2">
          <span>🎮 GRADE LEVEL CARTRIDGES (1 to 10)</span>
        </h2>
        <div className="grid grid-cols-5 sm:grid-cols-10 gap-2.5">
          {classes.map((cls) => {
            const isSelected = selectedClass === cls;
            return (
              <button
                key={cls}
                onClick={() => setSelectedClass(cls)}
                className={`h-16 flex flex-col items-center justify-center pixel-corners pixel-border hard-shadow hard-shadow-active font-pixel font-bold transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#bc000a] text-white ring-4 ring-[#1c1b1b]'
                    : 'bg-[#ffffff] text-[#1c1b1b] hover:bg-[#eae7e7]'
                }`}
              >
                <span className="text-[10px] opacity-80">CLASS</span>
                <span className="text-xl leading-none">{cls}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Subject Cartridge Selection */}
      <div className="space-y-3">
        <h2 className="font-pixel text-xs font-bold text-[#1c1b1b] uppercase flex items-center gap-2">
          <span>🧪 SUBJECT CARTRIDGES</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {subjects.map((sub) => {
            const isSelected = selectedSubject === sub.id;
            return (
              <button
                key={sub.id}
                onClick={() => setSelectedSubject(sub.id)}
                className={`p-5 pixel-corners pixel-border hard-shadow hard-shadow-active text-left flex items-center justify-between transition-all cursor-pointer ${
                  isSelected
                    ? `${sub.bg} ring-4 ring-[#1c1b1b]`
                    : 'bg-[#ffffff] text-[#1c1b1b] hover:bg-[#eae7e7]'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-3xl">{sub.icon}</span>
                  <div>
                    <span className="font-headline font-bold text-lg block">{sub.label}</span>
                    <span className="font-pixel text-[11px] font-semibold opacity-80">NCERT CLASS {selectedClass}</span>
                  </div>
                </div>
                {isSelected && <span className="font-pixel text-xs font-extrabold">▶ ACTIVE</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Chapters Cartridge List */}
      <div className="space-y-4 pt-4 border-t-[3px] border-[#1c1b1b]">
        <div className="flex items-center justify-between">
          <h2 className="font-headline font-bold text-2xl text-[#1c1b1b]">
            Class {selectedClass} {selectedSubject} Chapters ({chapters.length})
          </h2>
          <span className="font-pixel text-xs font-bold px-3 py-1 bg-[#fecb00] text-[#6e5700] pixel-border">
            RAG INDEX READY
          </span>
        </div>

        {loading ? (
          <div className="p-8 bg-[#ffffff] pixel-border text-center font-pixel text-sm font-bold text-[#bc000a] animate-pulse">
            LOADING NCERT CHAPTER INDEX FROM BACKEND...
          </div>
        ) : chapters.length === 0 ? (
          <div className="p-8 bg-[#ffffff] pixel-border text-center space-y-3">
            <p className="font-headline font-bold text-lg text-[#1c1b1b]">
              No chapters loaded for Class {selectedClass} {selectedSubject}
            </p>
            <p className="font-body text-xs text-[#5d3f3b]">
              Please check backend API connection or try Class 6 Science!
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {chapters.map((ch, idx) => (
              <div
                key={ch.id || idx}
                className="bg-[#ffffff] pixel-border p-5 pixel-corners hard-shadow flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-2 py-0.5 border border-[#1c1b1b]">
                      CHAPTER {idx + 1}
                    </span>
                    <span className="font-pixel text-[11px] text-[#5d3f3b] font-bold">
                      ID: {ch.id}
                    </span>
                  </div>
                  <h3 className="font-headline font-bold text-xl text-[#1c1b1b] mb-1">
                    {ch.title}
                  </h3>
                  <p className="font-body text-xs text-[#5d3f3b] line-clamp-2">
                    {ch.summary || `NCERT Curriculum chapter content for Class ${selectedClass} ${selectedSubject}.`}
                  </p>
                </div>

                <button
                  onClick={() => onSelectChapter(ch)}
                  className="w-full py-3 bg-[#006b27] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>START LESSON CHAT</span>
                  <span className="material-symbols-outlined text-base">play_arrow</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
