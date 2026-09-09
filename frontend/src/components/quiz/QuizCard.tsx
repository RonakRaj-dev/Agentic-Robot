import React, { useState } from 'react';
import { Award, CheckCircle2, AlertCircle, Star, Sparkles, RefreshCw } from 'lucide-react';
import type { QuizQuestion } from '../../api/client';

interface QuizCardProps {
  questions: QuizQuestion[];
  chapterTitle: string;
}

export const QuizCard: React.FC<QuizCardProps> = ({ questions, chapterTitle }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isAnswered, setIsAnswered] = useState(false);
  const [score, setScore] = useState(0);
  const [quizFinished, setQuizFinished] = useState(false);

  if (!questions || questions.length === 0) {
    return <div className="p-8 text-center text-[#494454] font-bold">No quiz available for this chapter yet.</div>;
  }

  const currentQ = questions[currentIndex];

  const handleSelectOption = (key: string) => {
    if (isAnswered) return;
    setSelectedOption(key);
    setIsAnswered(true);
    if (key === currentQ.correctKey) {
      setScore((prev) => prev + 1);
    }
  };

  const handleNext = () => {
    setSelectedOption(null);
    setIsAnswered(false);
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setQuizFinished(true);
    }
  };

  if (quizFinished) {
    const starRating = Math.round((score / questions.length) * 5);

    return (
      <div className="max-w-md mx-auto bg-[#ffffff] rounded-[2.5rem] p-8 text-center border-4 border-[#6b38d4] chunky-shadow-primary space-y-6">
        <div className="w-24 h-24 bg-[#b2f746] text-[#121f00] border-4 border-[#446900] rounded-full flex items-center justify-center mx-auto chunky-shadow-secondary animate-bounce">
          <Award className="w-12 h-12" />
        </div>

        <div className="space-y-2">
          <span className="px-3.5 py-1 bg-[#ffdcc5] text-[#301400] font-extrabold text-xs rounded-full border border-[#904800]">
            Official NCERT AI Certificate
          </span>
          <h2 className="font-heading text-3xl font-extrabold text-[#181445]">Chapter Master! 🌟</h2>
          <p className="text-xs text-[#494454] font-bold">{chapterTitle}</p>
        </div>

        {/* Star Rating */}
        <div className="flex justify-center gap-2">
          {[1, 2, 3, 4, 5].map((star) => (
            <Star
              key={star}
              className={`w-8 h-8 ${
                star <= starRating ? 'text-[#fb923c] fill-[#fb923c] animate-pulse' : 'text-[#cbc3d7]'
              }`}
            />
          ))}
        </div>

        <div className="p-4 bg-[#efebff] rounded-2xl border-2 border-[#6b38d4]/30">
          <p className="text-sm font-extrabold text-[#181445]">
            Final Score: {score} / {questions.length} Correct
          </p>
        </div>

        <button
          onClick={() => {
            setCurrentIndex(0);
            setSelectedOption(null);
            setIsAnswered(false);
            setScore(0);
            setQuizFinished(false);
          }}
          className="w-full py-4 bg-[#fb923c] hover:bg-[#b55d00] text-white font-heading font-extrabold rounded-2xl border-2 border-[#904800] chunky-shadow-tertiary btn-press cursor-pointer flex items-center justify-center gap-2 transition-transform"
        >
          <RefreshCw className="w-5 h-5" />
          <span>Retry Quiz</span>
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto bg-[#ffffff] rounded-[2rem] p-8 border-2 border-[#6b38d4] chunky-shadow-primary space-y-6">
      {/* Header Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-[#fb923c]" />
          <span className="font-heading font-extrabold text-sm text-[#181445]">
            Question {currentIndex + 1} of {questions.length}
          </span>
        </div>
        <span className="text-xs font-extrabold text-[#121f00] bg-[#b2f746] px-3.5 py-1 rounded-full border border-[#446900]">
          Quiz Quest Mode
        </span>
      </div>

      {/* Question Text */}
      <h3 className="font-heading text-xl font-extrabold text-[#181445] leading-snug">
        {currentQ.question}
      </h3>

      {/* Multiple Choice Options */}
      <div className="space-y-3">
        {currentQ.options.map((opt) => {
          let btnStyle = "bg-[#fcf8ff] border-[#cbc3d7] text-[#181445] hover:bg-[#efebff]";

          if (isAnswered) {
            if (opt.key === currentQ.correctKey) {
              btnStyle = "bg-[#b2f746] text-[#121f00] border-[#446900] chunky-shadow-secondary";
            } else if (opt.key === selectedOption) {
              btnStyle = "bg-[#ffdcc5] text-[#301400] border-[#904800]";
            } else {
              btnStyle = "bg-[#fcf8ff] border-[#cbc3d7] text-[#7b7486] opacity-50";
            }
          }

          return (
            <button
              key={opt.key}
              onClick={() => handleSelectOption(opt.key)}
              className={`w-full p-4 rounded-2xl border-2 text-left font-bold text-sm transition-all cursor-pointer flex items-center justify-between btn-press ${btnStyle}`}
            >
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-xl bg-white/60 flex items-center justify-center font-extrabold text-xs border border-[#181445]/20">
                  {opt.key}
                </span>
                <span>{opt.text}</span>
              </div>

              {isAnswered && opt.key === currentQ.correctKey && (
                <CheckCircle2 className="w-5 h-5 text-[#446900]" />
              )}
            </button>
          );
        })}
      </div>

      {/* Non-Punitive Educational Feedback */}
      {isAnswered && (
        <div className={`p-4 rounded-2xl border-2 space-y-1 ${
          selectedOption === currentQ.correctKey 
            ? 'bg-[#b2f746]/40 border-[#446900] text-[#121f00]' 
            : 'bg-[#ffdcc5]/60 border-[#904800] text-[#301400]'
        }`}>
          <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider">
            {selectedOption === currentQ.correctKey ? (
              <span className="flex items-center gap-1 text-[#446900]"><CheckCircle2 className="w-4 h-4" /> Great job! Correct!</span>
            ) : (
              <span className="flex items-center gap-1 text-[#904800]"><AlertCircle className="w-4 h-4" /> Nice try! Here's why:</span>
            )}
          </div>
          <p className="text-xs font-semibold leading-relaxed">{currentQ.explanation}</p>
        </div>
      )}

      {/* Next Button */}
      {isAnswered && (
        <button
          onClick={handleNext}
          className="w-full py-4 bg-[#fb923c] hover:bg-[#b55d00] text-white font-heading font-extrabold rounded-2xl border-2 border-[#904800] chunky-shadow-tertiary btn-press cursor-pointer transition-transform"
        >
          {currentIndex + 1 < questions.length ? 'Next Question ➔' : 'See Final Results 🏆'}
        </button>
      )}
    </div>
  );
};
