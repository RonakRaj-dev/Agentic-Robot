import React from 'react';
import { BookOpen, Sparkles, Layers, Award, BarChart3, LogIn, User, LogOut } from 'lucide-react';
import { DEMO_MODE } from '../../api/client';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedClass: number;
  selectedSubject: string;
  user?: { username: string; role: string; class_level: number } | null;
  onOpenLogin?: () => void;
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  selectedClass,
  selectedSubject,
  user,
  onOpenLogin,
  onLogout,
}) => {
  return (
    <header className="sticky top-0 z-50 bg-[#fcf8ff]/85 backdrop-blur-md border-b-4 border-[#6b38d4] chunky-shadow-primary px-4 py-3 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <div 
          onClick={() => setActiveTab('landing')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-11 h-11 rounded-2xl bg-[#8455ef] text-white flex items-center justify-center border-2 border-[#6b38d4] chunky-shadow-primary group-hover:scale-105 transition-transform">
            <BookOpen className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-heading text-2xl font-bold text-[#181445] tracking-tight">EduFun Quest</span>
              {DEMO_MODE ? (
                <span className="px-2.5 py-0.5 text-xs font-bold bg-[#b2f746] text-[#121f00] rounded-full border border-[#446900]">
                  DEMO MODE
                </span>
              ) : (
                <span className="px-2.5 py-0.5 text-xs font-bold bg-[#22d3ee]/20 text-[#0891b2] rounded-full border border-[#0891b2]">
                  LIVE API
                </span>
              )}
            </div>
            <p className="text-xs text-[#494454] font-semibold">CurioText AI NCERT Interactive Class 1–10</p>
          </div>
        </div>

        {/* Selected Context Indicator */}
        <div className="hidden md:flex items-center gap-2 px-4 py-1.5 bg-[#efebff] rounded-full border-2 border-[#6b38d4]/30 text-xs font-bold text-[#181445]">
          <span className="w-2.5 h-2.5 rounded-full bg-[#a3e635] animate-pulse" />
          <span>Class {selectedClass}</span>
          <span className="text-[#7b7486]">•</span>
          <span className="capitalize">{selectedSubject ? selectedSubject.replace(/_/g, ' ') : ''}</span>
        </div>

        {/* Main Navigation Links */}
        <nav className="flex items-center gap-1 md:gap-2">
          <button
            onClick={() => setActiveTab('explorer')}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'explorer'
                ? 'bg-[#8455ef] text-white border-2 border-[#6b38d4] chunky-shadow-primary'
                : 'text-[#181445] hover:bg-[#efebff]'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Chapter Explorer</span>
          </button>

          <button
            onClick={() => setActiveTab('flashcards')}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'flashcards'
                ? 'bg-[#b2f746] text-[#121f00] border-2 border-[#446900] chunky-shadow-secondary'
                : 'text-[#181445] hover:bg-[#efebff]'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Flashcards</span>
          </button>

          <button
            onClick={() => setActiveTab('quiz')}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'quiz'
                ? 'bg-[#fb923c] text-white border-2 border-[#904800] chunky-shadow-tertiary'
                : 'text-[#181445] hover:bg-[#efebff]'
            }`}
          >
            <Award className="w-4 h-4" />
            <span>Quiz Mode</span>
          </button>

          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'dashboard'
                ? 'bg-[#6b38d4] text-white border-2 border-[#6b38d4] chunky-shadow-primary'
                : 'text-[#181445] hover:bg-[#efebff]'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span className="hidden sm:inline">Analytics</span>
          </button>

          {user ? (
            <div className="flex items-center gap-2 ml-2 pl-2 border-l-2 border-[#cbc3d7]">
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#ffdcc5] text-[#301400] border-2 border-[#904800] rounded-xl text-xs font-bold">
                <User className="w-3.5 h-3.5 text-[#904800]" />
                <span>{user.username} ({user.role})</span>
              </div>
              <button
                onClick={onLogout}
                title="Sign Out"
                className="p-2 text-[#494454] hover:text-[#ba1a1a] hover:bg-[#ffdad6] rounded-xl transition-all"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenLogin}
              className="flex items-center gap-1.5 px-4 py-2 ml-1 rounded-xl text-sm font-bold bg-[#6b38d4] text-white border-2 border-[#6b38d4] chunky-shadow-primary btn-press hover:scale-105 transition-all"
            >
              <LogIn className="w-4 h-4" />
              <span>Sign In</span>
            </button>
          )}
        </nav>
      </div>
    </header>
  );
};

