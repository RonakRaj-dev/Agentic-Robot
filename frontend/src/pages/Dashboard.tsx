import React from 'react';
import { BarChart3, BookOpen, CheckCircle, Clock, TrendingUp } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
} from 'recharts';

const quizScoreData = [
  { chapter: 'Ch 1 Food', score: 90 },
  { chapter: 'Ch 2 Numbers', score: 85 },
  { chapter: 'Ch 3 Plants', score: 95 },
  { chapter: 'Ch 4 Energy', score: 80 },
];

const timeSpentData = [
  { day: 'Mon', minutes: 25 },
  { day: 'Tue', minutes: 40 },
  { day: 'Wed', minutes: 30 },
  { day: 'Thu', minutes: 50 },
  { day: 'Fri', minutes: 45 },
];

interface DashboardProps {
  selectedClass?: number;
  user?: { username: string; role: string; class_level: number } | null;
}

export const Dashboard: React.FC<DashboardProps> = ({ selectedClass = 6, user }) => {
  const activeClass = user?.class_level || selectedClass || 6;
  const roleLabel = user?.role ? `${user.role.toUpperCase()} PORTAL` : 'TEACHER & ADMINISTRATOR PORTAL';

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#ffffff] p-6 rounded-[2rem] border-2 border-[#6b38d4] chunky-shadow-primary">
        <div>
          <span className="text-xs font-extrabold text-[#6b38d4] uppercase tracking-wider">{roleLabel}</span>
          <h1 className="font-heading text-2xl font-extrabold text-[#181445]">Class {activeClass} Student Analytics Dashboard</h1>
          <p className="text-xs text-[#494454] font-medium">
            {user ? `Welcome back, ${user.username}! Live summary for Grade ${activeClass}.` : `Live summary of student interaction, quiz scores, and AI agent usage for Class ${activeClass}.`}
          </p>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 bg-[#b2f746] text-[#121f00] font-extrabold text-xs rounded-2xl border border-[#446900]">
          <TrendingUp className="w-4 h-4" />
          <span>Class Mastery: 88%</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-6">
        {[
          { label: 'Chapters Completed', val: '12 / 16', icon: BookOpen, color: '#e3dfff', border: '#6b38d4' },
          { label: 'Avg Quiz Score', val: '88%', icon: CheckCircle, color: '#b2f746', border: '#446900' },
          { label: 'Questions Asked', val: '142 Queries', icon: BarChart3, color: '#ffdcc5', border: '#904800' },
          { label: 'Weekly Study Time', val: '3.2 Hours', icon: Clock, color: '#cff4fc', border: '#0891b2' },
        ].map((kpi) => {
          const IconComp = kpi.icon;
          return (
            <div key={kpi.label} className="bg-[#ffffff] p-6 rounded-[2rem] border-2 space-y-2 chunky-shadow-primary hover:-translate-y-1 transition-transform" style={{ borderColor: kpi.border }}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-extrabold text-[#7b7486]">{kpi.label}</span>
                <div 
                  className="w-9 h-9 rounded-xl flex items-center justify-center text-[#181445] border border-[#181445]/20"
                  style={{ backgroundColor: kpi.color }}
                >
                  <IconComp className="w-4 h-4" />
                </div>
              </div>
              <p className="font-heading text-2xl font-extrabold text-[#181445]">{kpi.val}</p>
            </div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Quiz Scores per Chapter Bar Chart */}
        <div className="bg-[#ffffff] p-6 rounded-[2rem] border-2 border-[#6b38d4] chunky-shadow-primary space-y-4">
          <h3 className="font-heading font-extrabold text-lg text-[#181445]">Quiz Scores by Chapter</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={quizScoreData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#efebff" />
                <XAxis dataKey="chapter" tick={{ fontSize: 12, fill: '#181445' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#181445' }} />
                <Tooltip />
                <Bar dataKey="score" fill="#6b38d4" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Weekly Study Time Line Chart */}
        <div className="bg-[#ffffff] p-6 rounded-[2rem] border-2 border-[#6b38d4] chunky-shadow-primary space-y-4">
          <h3 className="font-heading font-extrabold text-lg text-[#181445]">Daily Learning Minutes</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeSpentData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#efebff" />
                <XAxis dataKey="day" tick={{ fontSize: 12, fill: '#181445' }} />
                <YAxis tick={{ fontSize: 12, fill: '#181445' }} />
                <Tooltip />
                <Line type="monotone" dataKey="minutes" stroke="#6b38d4" strokeWidth={4} dot={{ r: 6, fill: '#b2f746', stroke: '#446900', strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
