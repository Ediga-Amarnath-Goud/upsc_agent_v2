import StatusBadge from '../ui/StatusBadge';
import { useProfile } from '../../hooks/useQueries';

export default function TopBar() {
  const { data: profile } = useProfile();

  return (
    <header className="h-[60px] border-b border-white/5 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <StatusBadge label="ONLINE" color="green" />
        <StatusBadge label="SAFE MODE" color="yellow" />
      </div>

      <div className="flex-1 max-w-[500px] mx-8">
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary text-sm">🔍</span>
          <input
            type="text"
            placeholder="Search Topics, PYQs, Notes, Sessions..."
            className="w-full bg-white/5 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-accent-orange">🔥</span>
          <span className="text-text-secondary">Flame:</span>
          <span className="text-white font-semibold">68 DAYS</span>
        </div>

        <div className="flex items-center gap-3 pl-4 border-l border-white/10">
          <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center text-xs font-bold text-accent-blue">
            {profile?.name ? profile.name.charAt(0).toUpperCase() : 'U'}
          </div>
          <div className="text-sm">
            <div className="text-white font-medium">{profile?.name || 'Student'}</div>
            <div className="text-text-secondary text-xs">ELO: {profile?.current_elo || 1200}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
