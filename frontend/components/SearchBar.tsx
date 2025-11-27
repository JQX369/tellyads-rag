'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query)}`);
    }
  };

  return (
    <form onSubmit={handleSearch} className="w-full relative group">
      <div 
        className={`
          absolute -inset-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full opacity-20 group-hover:opacity-40 transition duration-500 blur-lg
          ${isFocused ? 'opacity-60 blur-xl' : ''}
        `}
      />
      <div className="relative flex items-center">
        <Search 
          className={`absolute left-5 w-6 h-6 transition-colors duration-300 ${isFocused ? 'text-blue-400' : 'text-slate-400'}`} 
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Describe the ad you're looking for..."
          className="w-full h-16 pl-14 pr-6 bg-white/10 backdrop-blur-xl border border-white/10 rounded-full text-lg text-white placeholder-slate-400 focus:outline-none focus:bg-white/15 focus:border-white/20 transition-all duration-300 shadow-2xl"
        />
        <div className="absolute right-3 p-1.5 bg-white/10 rounded-full text-xs font-medium text-slate-400 border border-white/5 hidden sm:block">
          ⏎
        </div>
      </div>
    </form>
  );
}
