import React, { useEffect, useState } from 'react';
import { fetchQuiz } from '../api/client';
import type { QuizQuestion } from '../api/client';
import { QuizCard } from '../components/quiz/QuizCard';

interface QuizPageProps {
  chapterId: string;
  chapterTitle: string;
  classLevel?: number;
  subject?: string;
}

export const QuizPage: React.FC<QuizPageProps> = ({
  chapterId,
  chapterTitle,
  classLevel = 6,
  subject = 'Science',
}) => {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);

  useEffect(() => {
    fetchQuiz(chapterId, classLevel, subject, chapterTitle).then(setQuestions);
  }, [chapterId, classLevel, subject, chapterTitle]);

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
      {/* Header Badge */}
      <div className="bg-[#ffffff] pixel-border p-6 pixel-corners hard-shadow text-center space-y-2">
        <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#fecb00] text-[#6e5700] px-3 py-1 border border-[#1c1b1b] inline-block uppercase">
          🏆 ROBOT QUIZ ARCADE
        </span>
        <h1 className="font-headline font-bold text-3xl text-[#1c1b1b]">
          Quiz Challenge: {chapterTitle}
        </h1>
        <p className="font-body text-sm text-[#5d3f3b] max-w-lg mx-auto">
          Answer chapter questions to earn XP and level up EduBot's mastery meter!
        </p>
      </div>

      <QuizCard questions={questions} chapterTitle={chapterTitle} />
    </div>
  );
};
