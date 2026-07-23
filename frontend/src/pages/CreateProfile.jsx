import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function CreateProfile() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');

  const isValid = name.trim().length >= 2 && age >= 10 && age <= 100 && gender;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isValid) return;
    localStorage.setItem('profile_draft', JSON.stringify({
      name: name.trim(), age: Number(age), gender,
    }));
    navigate('/consent');
  };

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#0A0A0A] px-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-green flex items-center justify-center mx-auto mb-4">
            <span className="text-xl font-bold text-white">U</span>
          </div>
          <h1 className="text-2xl font-bold">Create Your Profile</h1>
          <p className="text-text-secondary text-sm mt-1">Tell us a bit about yourself</p>
        </div>

        <form onSubmit={handleSubmit} className="glass p-8 space-y-5">
          <div>
            <label className="block text-sm text-text-secondary mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50 transition"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1.5">Age</label>
            <input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="Your age"
              min={10}
              max={100}
              className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50 transition"
            />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1.5">Gender</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-accent-blue/50 transition appearance-none"
            >
              <option value="" disabled className="bg-[#1a1a1a]">Select gender</option>
              <option value="Male" className="bg-[#1a1a1a]">Male</option>
              <option value="Female" className="bg-[#1a1a1a]">Female</option>
              <option value="Other" className="bg-[#1a1a1a]">Other</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={!isValid}
            className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium hover:bg-accent-blue/80 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Continue
          </button>
        </form>
      </div>
    </div>
  );
}
