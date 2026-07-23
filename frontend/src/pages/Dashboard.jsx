import ActiveSession from '../components/cards/ActiveSession';
import TodaysMission from '../components/cards/TodaysMission';
import PendingPYQs from '../components/cards/PendingPYQs';
import BacklogsDue from '../components/cards/BacklogsDue';
import SessionStatus from '../components/cards/SessionStatus';
import SubjectProgress from '../components/cards/SubjectProgress';
import PerformanceSnapshot from '../components/cards/PerformanceSnapshot';
import WeeklyHeatmap from '../components/cards/WeeklyHeatmap';
import StudyHours from '../components/cards/StudyHours';
import QuickActions from '../components/cards/QuickActions';
import SystemOperations from '../components/cards/SystemOperations';
import RecentActivity from '../components/cards/RecentActivity';

export default function Dashboard() {
  return (
    <div className="grid grid-cols-4 gap-4 auto-rows-auto">
      {/* Row 1 */}
      <ActiveSession />
      <TodaysMission />
      <div className="flex flex-col gap-4">
        <PendingPYQs />
        <BacklogsDue />
      </div>
      <SessionStatus />

      {/* Row 2 */}
      <SubjectProgress />
      <PerformanceSnapshot />
      <WeeklyHeatmap />
      <div className="flex flex-col gap-4">
        <StudyHours />
        <QuickActions />
      </div>

      {/* Row 3 */}
      <SystemOperations />

      {/* Row 4 - full width */}
      <RecentActivity />
    </div>
  );
}
