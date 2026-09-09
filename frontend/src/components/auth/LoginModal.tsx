import React, { useState } from 'react';
import { LogIn, UserPlus, X, GraduationCap, Lock, User } from 'lucide-react';
import { loginUser, registerUser } from '../../api/client';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: { username: string; role: string; class_level: number }) => void;
}

export function LoginModal({ isOpen, onClose, onLoginSuccess }: LoginModalProps) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  const [classLevel, setClassLevel] = useState<number>(6);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      if (isRegistering) {
        const res = await registerUser(username, password, role, classLevel);
        if (res.success && res.user) {
          onLoginSuccess(res.user);
          onClose();
        } else {
          setErrorMsg(res.error || 'Registration failed.');
        }
      } else {
        const res = await loginUser(username, password);
        if (res.success && res.user) {
          onLoginSuccess(res.user);
          onClose();
        } else {
          setErrorMsg(res.error || 'Invalid credentials or connection error.');
        }
      }
    } catch {
      setErrorMsg('An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#181445]/60 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-md bg-[#ffffff] rounded-[2.5rem] overflow-hidden border-4 border-[#6b38d4] chunky-shadow-primary">
        {/* Top Header Banner */}
        <div className="bg-[#6b38d4] p-6 text-white text-center relative border-b-2 border-[#181445]">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="inline-flex p-3 bg-[#b2f746] rounded-2xl mb-2 border-2 border-[#446900] chunky-shadow-secondary text-[#121f00]">
            <GraduationCap className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-extrabold font-heading tracking-tight text-white">
            {isRegistering ? 'Create Account' : 'Welcome Back!'}
          </h2>
          <p className="text-[#f3eeff] text-xs mt-1 font-medium">
            {isRegistering ? 'Register to access personalized AI learning' : 'Sign in to access your classroom robot assistant'}
          </p>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-[#ffdad6] border-2 border-[#ba1a1a] text-[#93000a] text-xs font-bold">
              ⚠️ {errorMsg}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-extrabold text-[#181445] uppercase tracking-wider">Username</label>
            <div className="relative">
              <User className="w-5 h-5 absolute left-3.5 top-3 text-[#7b7486]" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className="w-full pl-11 pr-4 py-2.5 rounded-2xl border-2 border-[#6b38d4] focus:outline-none focus:border-[#446900] text-sm font-semibold transition-all"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-extrabold text-[#181445] uppercase tracking-wider">Password</label>
            <div className="relative">
              <Lock className="w-5 h-5 absolute left-3.5 top-3 text-[#7b7486]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full pl-11 pr-4 py-2.5 rounded-2xl border-2 border-[#6b38d4] focus:outline-none focus:border-[#446900] text-sm font-semibold transition-all"
              />
            </div>
          </div>

          {isRegistering && (
            <>
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="space-y-1">
                  <label className="text-xs font-extrabold text-[#181445] uppercase tracking-wider">Role</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as 'student' | 'teacher')}
                    className="w-full px-3 py-2.5 rounded-2xl border-2 border-[#6b38d4] focus:outline-none focus:border-[#446900] text-sm bg-white font-bold"
                  >
                    <option value="student">🎓 Student</option>
                    <option value="teacher">👨‍🏫 Teacher</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-extrabold text-[#181445] uppercase tracking-wider">Class Level</label>
                  <select
                    value={classLevel}
                    onChange={(e) => setClassLevel(Number(e.target.value))}
                    className="w-full px-3 py-2.5 rounded-2xl border-2 border-[#6b38d4] focus:outline-none focus:border-[#446900] text-sm bg-white font-bold"
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((lvl) => (
                      <option key={lvl} value={lvl}>Class {lvl}</option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 mt-2 rounded-2xl bg-[#6b38d4] text-white border-2 border-[#6b38d4] chunky-shadow-primary btn-press font-heading font-extrabold text-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <span className="animate-pulse">Authenticating...</span>
            ) : isRegistering ? (
              <>
                <UserPlus className="w-5 h-5" /> Register Account
              </>
            ) : (
              <>
                <LogIn className="w-5 h-5" /> Sign In
              </>
            )}
          </button>

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => setIsRegistering(!isRegistering)}
              className="text-xs text-[#6b38d4] hover:underline font-extrabold"
            >
              {isRegistering ? 'Already have an account? Sign In' : "Don't have an account? Register Now"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
