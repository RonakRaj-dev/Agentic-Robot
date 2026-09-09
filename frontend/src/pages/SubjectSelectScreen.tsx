import React, { useState, useEffect } from 'react';
import type { Chapter } from '../api/client';
import { fetchChapters, fetchSubjects } from '../api/client';

interface SubjectSelectScreenProps {
  selectedClass: number;
  selectedSubject: string | null;
  onSelectSubject: (s: string) => void;
  onSelectChapter: (ch: Chapter) => void;
}

export const SubjectSelectScreen: React.FC<SubjectSelectScreenProps> = ({
  selectedClass,
  selectedSubject,
  onSelectSubject,
  onSelectChapter,
}) => {
  const [subjectsList, setSubjectsList] = useState<string[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);

  // 1. JIT Fetch valid subjects for the selected class from MongoDB
  useEffect(() => {
    setLoadingSubjects(true);
    fetchSubjects(selectedClass).then((subs) => {
      setSubjectsList(subs || []);
      setLoadingSubjects(false);
    });
  }, [selectedClass]);

  const activeSubj = selectedSubject && subjectsList.includes(selectedSubject)
    ? selectedSubject
    : null;

  // 2. JIT Fetch chapters for the selected class and subject
  useEffect(() => {
    if (activeSubj) {
      setLoadingChapters(true);
      fetchChapters(selectedClass, activeSubj).then((list) => {
        setChapters(list || []);
        setLoadingChapters(false);
      });
    } else {
      setChapters([]);
    }
  }, [selectedClass, activeSubj]);

  const getSubjectIcon = (subjName: string) => {
    const s = subjName.toLowerCase();
    if (s.includes('sci') && !s.includes('computer')) return { icon: 'science', bg: 'bg-[#72fe88] text-[#002107]' };
    if (s.includes('math')) return { icon: 'calculate', bg: 'bg-[#fecb00] text-[#6e5700]' };
    if (s.includes('soc') || s.includes('hist')) return { icon: 'public', bg: 'bg-[#ffdad5] text-[#930005]' };
    if (s.includes('eng')) return { icon: 'menu_book', bg: 'bg-[#e5e2e1] text-[#1c1b1b]' };
    if (s.includes('hin')) return { icon: 'translate', bg: 'bg-[#ffdad5] text-[#930005]' };
    if (s.includes('comp') || s.includes('tech')) return { icon: 'terminal', bg: 'bg-[#72fe88] text-[#002107]' };
    if (s.includes('env') || s.includes('evs')) return { icon: 'eco', bg: 'bg-[#72fe88] text-[#002107]' };
    return { icon: 'school', bg: 'bg-[#e5e2e1] text-[#1c1b1b]' };
  };

  const formatSubjectDisplayName = (subj: string | null): string => {
    if (!subj) return '';
    return subj.replace(/_/g, ' ');
  };

  return (
    <div className="flex-1 flex flex-col justify-start items-center px-6 pt-16 pb-24 w-full h-full max-w-6xl mx-auto overflow-y-auto">
      {/* Title Badge Header */}
      <div className="text-center mb-6">
        <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] inline-block uppercase mb-2">
          CLASS {selectedClass} MONGODB CURRICULUM
        </span>
        <h2 className="font-headline text-3xl font-black text-[#1c1b1b] uppercase">
          Select Subject & Chapter
        </h2>
      </div>

      {/* Dynamic JIT Subject Selection Grid */}
      <div className="w-full mb-8">
        {loadingSubjects ? (
          <div className="p-6 bg-[#ffffff] pixel-border text-center font-pixel text-xs font-bold text-[#bc000a] animate-pulse">
            JIT FETCHING CLASS {selectedClass} SUBJECTS FROM MONGODB...
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 w-full">
            {subjectsList.map((subName) => {
              const isSelected = activeSubj === subName;
              const style = getSubjectIcon(subName);
              return (
                <button
                  key={subName}
                  onClick={() => onSelectSubject(subName)}
                  className={`p-4 md:p-5 pixel-border brutal-shadow brutal-button-active text-left flex items-center justify-between transition-all cursor-pointer min-w-0 w-full overflow-hidden ${
                    isSelected
                      ? `${style.bg} ring-4 ring-[#1c1b1b]`
                      : 'bg-[#ffffff] text-[#1c1b1b] hover:bg-[#eae7e7]'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1 mr-2">
                    <span className="material-symbols-outlined text-3xl md:text-4xl shrink-0">{style.icon}</span>
                    <div className="min-w-0 flex-1">
                      <span className="font-headline font-bold text-base md:text-lg block break-words leading-tight uppercase">
                        {formatSubjectDisplayName(subName)}
                      </span>
                      <span className="font-pixel text-[11px] font-semibold opacity-80 block mt-0.5">CLASS {selectedClass} NCERT</span>
                    </div>
                  </div>
                  {isSelected && <span className="font-pixel text-xs font-extrabold shrink-0">▶ ACTIVE</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Chapter Cards List */}
      {activeSubj ? (
        <div className="w-full space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between border-b-[3px] border-[#1c1b1b] pb-2">
            <h3 className="font-headline font-bold text-2xl text-[#1c1b1b] uppercase">
              Class {selectedClass} {formatSubjectDisplayName(activeSubj)} Chapters ({chapters.length})
            </h3>
            <span className="font-pixel text-xs font-bold px-3 py-1 bg-[#fecb00] text-[#6e5700] pixel-border">
              MONGODB JIT RAG INDEX
            </span>
          </div>

          {loadingChapters ? (
            <div className="p-8 bg-[#ffffff] pixel-border text-center font-pixel text-xs font-bold text-[#bc000a] animate-pulse">
              FETCHING CLASS {selectedClass} {formatSubjectDisplayName(activeSubj).toUpperCase()} CHAPTERS FROM MONGODB...
            </div>
          ) : chapters.length === 0 ? (
            <div className="p-8 bg-[#ffffff] pixel-border text-center space-y-3">
              <p className="font-headline font-bold text-lg text-[#1c1b1b]">
                No chapters loaded for Class {selectedClass} {formatSubjectDisplayName(activeSubj)}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {chapters.map((ch, idx) => (
                <div
                  key={ch.id || idx}
                  className="bg-[#ffffff] pixel-border p-5 brutal-shadow flex flex-col justify-between space-y-4"
                >
                  <div>
                    <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-2 py-0.5 border border-[#1c1b1b]">
                      CHAPTER {ch.chapterNumber || idx + 1}
                    </span>
                    <h4 className="font-headline font-bold text-xl text-[#1c1b1b] mt-2 mb-1">
                      {ch.title}
                    </h4>
                    <p className="font-body text-xs text-[#5d3f3b] line-clamp-2">
                      {ch.summary || `Official NCERT textbook chapter content for Class ${selectedClass} ${formatSubjectDisplayName(activeSubj)}.`}
                    </p>
                  </div>

                  <button
                    onClick={() => onSelectChapter(ch)}
                    className="w-full py-3 bg-[#006b27] text-white font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>START LESSON CHAT</span>
                    <span className="material-symbols-outlined text-base">play_arrow</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="w-full p-12 bg-[#ffffff] pixel-border brutal-shadow text-center space-y-4 max-w-2xl mt-4 animate-fadeIn">
          <div className="text-5xl">👈</div>
          <h3 className="font-headline font-black text-2xl text-[#1c1b1b] uppercase">
            Select a Subject Above
          </h3>
          <p className="font-pixel text-xs text-[#5d3f3b]">
            Choose any dynamic curriculum subject listed above to explore its chapters directly from the MongoDB knowledge base.
          </p>
        </div>
      )}
    </div>
  );
};
