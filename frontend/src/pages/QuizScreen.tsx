import React, { useState, useEffect } from 'react';
import type { QuizQuestion } from '../api/client';
import { fetchQuiz } from '../api/client';
import { ArcadeLoader } from '../components/ArcadeLoader';

interface QuizScreenProps {
  chapterId: string;
  chapterTitle: string;
  classLevel: number;
  subject: string;
  onOpenAnalytics: () => void;
}

export const QuizScreen: React.FC<QuizScreenProps> = ({
  chapterId,
  chapterTitle,
  classLevel,
  subject,
  onOpenAnalytics,
}) => {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [showRewardModal, setShowRewardModal] = useState(false);
  const [isQuizComplete, setIsQuizComplete] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    fetchQuiz(chapterId, classLevel, subject, chapterTitle).then((fetched) => {
      setQuestions(fetched || []);
      setCurrentIndex(0);
      setCorrectCount(0);
      setSelectedOption(null);
      setShowRewardModal(false);
      setIsQuizComplete(false);
      setIsLoading(false);
    }).catch(() => {
      setIsLoading(false);
    });
  }, [chapterId, classLevel, subject, chapterTitle]);

  const currentQ = questions[currentIndex] || {
    question: `What is the primary concept studied in ${chapterTitle}?`,
    options: [
      { key: 'A', text: `Core principles and rules of ${chapterTitle}` },
      { key: 'B', text: 'Unrelated observations' },
      { key: 'C', text: 'Arbitrary assumptions' },
      { key: 'D', text: 'None of the above' },
    ],
    correctKey: 'A',
  };


  const handleConfirm = () => {
    if (!selectedOption) return;

    let newCorrect = correctCount;
    if (selectedOption === currentQ.correctKey) {
      newCorrect += 1;
      setCorrectCount(newCorrect);
    }

    if (currentIndex < Math.max(questions.length - 1, 9)) {
      setCurrentIndex((i) => i + 1);
      setSelectedOption(null);
    } else {
      // Completed all 10 questions!
      setIsQuizComplete(true);
      if (newCorrect >= 6) {
        setShowRewardModal(true);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-16 pb-24 w-full h-full max-w-6xl mx-auto overflow-y-auto relative">
      {/* Header & Segmented Progress Bar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
          <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] inline-block uppercase">
            QUIZ ARCADE • CLASS {classLevel} {subject}
          </span>
          <h2 className="font-headline font-bold text-2xl text-[#1c1b1b] mt-1">
            {chapterTitle}
          </h2>
        </div>

        {/* Progress Bar & Score Counter */}
        <div className="bg-[#ffffff] border-[3px] border-[#1c1b1b] px-6 py-3 brutal-shadow">
          <div className="flex justify-between items-center gap-4">
            <h3 className="font-pixel text-xs font-bold text-[#bc000a] uppercase tracking-widest">
              QUESTION {currentIndex + 1} / {Math.max(questions.length, 10)}
            </h3>
            <span className="font-pixel text-xs font-bold text-[#006b27] bg-[#72fe88] px-2.5 py-0.5 border border-[#1c1b1b]">
              CORRECT: {correctCount} / 10
            </span>
          </div>

          <div className="flex gap-1 mt-2">
            {Array.from({ length: 10 }).map((_, idx) => (
              <div
                key={idx}
                className={`h-2.5 w-4 border border-[#1c1b1b] ${
                  idx <= currentIndex ? 'bg-[#bc000a]' : 'bg-[#e5e2e1]'
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Main Split View: Left Question Box vs Right Option Controls OR Arcade Loader */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center my-auto py-8">
          <ArcadeLoader
            title="Loading Chapter Quiz..."
            subtitle={`Loading questions for ${chapterTitle}...`}
            defaultVariant="scifi-server"
          />
        </div>
      ) : !isQuizComplete ? (

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center flex-1">


          {/* Left Pane: Question Box & Robot Character */}
          <div className="md:col-span-7 flex flex-col gap-6">
            <div className="bg-[#ffffff] pixel-border p-8 brutal-shadow-lg relative">
              <div className="absolute -top-4 -left-4 bg-[#fecb00] border-[3px] border-[#1c1b1b] p-2 brutal-shadow transform -rotate-3">
                <span className="material-symbols-outlined text-[#6e5700] text-3xl">psychology</span>
              </div>
              <h1 className="font-headline font-black text-2xl md:text-3xl text-[#1c1b1b] mt-3 mb-2">
                {currentQ.question}
              </h1>
              <p className="font-body text-sm text-[#5d3f3b]">
                Select the best answer from the options on the right.
              </p>
            </div>

            {/* Robot Character & Speech Bubble */}
            <div className="flex items-center gap-4">
              <div className="w-24 h-24 border-[3px] border-[#1c1b1b] bg-[#fecb00] brutal-shadow flex items-center justify-center text-4xl shrink-0">
                🤖
              </div>
              <div className="bg-[#ffffff] border-[3px] border-[#1c1b1b] p-4 brutal-shadow relative">
                <p className="font-body text-sm font-bold text-[#1c1b1b]">
                  Score 6 or more correct answers to unlock special in-app rewards!
                </p>
              </div>
            </div>
          </div>

          {/* Right Pane: Option Controls */}
          <div className="md:col-span-5 flex flex-col gap-3">
            {currentQ.options.map((opt) => {
              const isSelected = selectedOption === opt.key;
              return (
                <button
                  key={opt.key}
                  onClick={() => setSelectedOption(opt.key)}
                  className={`w-full text-left p-5 border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active flex items-center gap-4 transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#fecb00] text-[#6e5700] ring-4 ring-[#1c1b1b] translate-x-1'
                      : 'bg-[#ffffff] text-[#1c1b1b] hover:bg-[#eae7e7]'
                  }`}
                >
                  <div className="w-10 h-10 flex items-center justify-center bg-[#f0eded] border-[3px] border-[#1c1b1b] font-headline text-lg font-bold text-[#1c1b1b]">
                    {opt.key}
                  </div>
                  <span className="font-headline font-bold text-lg flex-1">{opt.text}</span>
                </button>
              );
            })}

            <button
              onClick={handleConfirm}
              disabled={!selectedOption}
              className="mt-4 h-16 w-full flex items-center justify-center gap-2 bg-[#bc000a] border-[3px] border-[#1c1b1b] text-white font-headline text-xl font-bold uppercase brutal-shadow brutal-button-active disabled:opacity-50 cursor-pointer"
            >
              <span>CONFIRM ANSWER</span>
              <span className="material-symbols-outlined text-2xl">send</span>
            </button>
          </div>
        </div>
      ) : (
        /* Quiz Summary Screen */
        <div className="bg-[#ffffff] pixel-border p-8 brutal-shadow max-w-2xl mx-auto text-center space-y-6 my-auto">
          <div className="w-20 h-20 bg-[#72fe88] text-[#002107] border-[3px] border-[#1c1b1b] rounded-full flex items-center justify-center mx-auto text-4xl brutal-shadow">
            🏆
          </div>
          <h2 className="font-headline font-black text-3xl text-[#1c1b1b]">
            Quiz Completed!
          </h2>
          <p className="font-headline text-xl font-bold text-[#bc000a]">
            Your Score: {correctCount} / 10 Correct ({correctCount * 10}%)
          </p>

          {correctCount >= 6 ? (
            <div className="p-4 bg-[#fecb00] text-[#6e5700] border-[3px] border-[#1c1b1b] brutal-shadow space-y-2">
              <span className="font-pixel text-xs font-bold uppercase block">🎉 REWARD GRANTED!</span>
              <p className="font-headline font-bold text-lg">
                You scored 6+ correct! You unlocked the Master Explorer Badge & Analytics Dashboard!
              </p>
              <button
                onClick={onOpenAnalytics}
                className="mt-3 px-6 py-3 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active cursor-pointer"
              >
                VIEW UNLOCKED ANALYTICS ➔
              </button>
            </div>
          ) : (
            <p className="font-body text-sm text-[#5d3f3b]">
              Score 6 or more to unlock special rewards! Try again or review flashcards.
            </p>
          )}
        </div>
      )}

      {/* Arcade Reward Unlocked Modal (Triggered on 6+ Correct Answers) */}
      {showRewardModal && (
        <div className="fixed inset-0 z-50 bg-[#1c1b1b]/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#ffffff] border-[4px] border-[#1c1b1b] p-8 max-w-lg w-full brutal-shadow-lg text-center space-y-6 animate-bounce">
            <div className="w-24 h-24 bg-[#fecb00] border-[3px] border-[#1c1b1b] flex items-center justify-center mx-auto text-5xl brutal-shadow">
              👑
            </div>
            <div className="space-y-2">
              <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] uppercase inline-block">
                ARCADE REWARD UNLOCKED!
              </span>
              <h2 className="font-headline font-black text-3xl text-[#1c1b1b]">
                CONGRATULATIONS!
              </h2>
              <p className="font-body text-base font-semibold text-[#5d3f3b]">
                You correctly answered {correctCount} out of 10 questions!
              </p>
            </div>

            <div className="p-4 bg-[#72fe88] text-[#002107] border-[3px] border-[#1c1b1b] brutal-shadow text-left space-y-2 font-pixel text-xs font-bold">
              <p>✔ UNLOCKED: Golden EduBot Mascot Skin</p>
              <p>✔ UNLOCKED: Student Telemetry Analytics Dashboard</p>
              <p>✔ GRANTED: +500 Bonus Quiz XP</p>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setShowRewardModal(false)}
                className="flex-1 py-3 bg-[#f0eded] text-[#1c1b1b] font-pixel text-xs font-bold uppercase border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active cursor-pointer"
              >
                CONTINUE
              </button>
              <button
                onClick={() => {
                  setShowRewardModal(false);
                  onOpenAnalytics();
                }}
                className="flex-1 py-3 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active cursor-pointer"
              >
                OPEN ANALYTICS ➔
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
