import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { DashboardPage } from './pages/DashboardPage';
import { SuspectQueuePage } from './pages/SuspectQueuePage';
import { SuspectDetailPage } from './pages/SuspectDetailPage';
import { MembersPage } from './pages/MembersPage';
import { PipelineMonitorPage } from './pages/PipelineMonitorPage';
import { ReviewsPage } from './pages/ReviewsPage';

export function App() {
  const [currentRoute, setCurrentRoute] = useState(
    window.location.hash.replace(/^#\/?/, '') || 'dashboard'
  );

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#\/?/, '') || 'dashboard';
      setCurrentRoute(hash);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (path) => {
    window.location.hash = `/${path}`;
    setCurrentRoute(path);
  };

  // Route parser
  let pageContent = null;
  const [routeBase, routeQuery] = currentRoute.split('?');
  const searchParams = new URLSearchParams(routeQuery || '');

  if (routeBase === 'dashboard') {
    pageContent = <DashboardPage onNavigate={navigate} />;
  } else if (routeBase.startsWith('suspect/')) {
    const suspectId = routeBase.replace('suspect/', '');
    pageContent = (
      <SuspectDetailPage
        suspectId={suspectId}
        onBack={() => navigate('suspects')}
        onNavigateMember={(beneId) => navigate(`member/${beneId}`)}
      />
    );
  } else if (routeBase === 'suspects') {
    const initialSearch = searchParams.get('search') || '';
    pageContent = (
      <SuspectQueuePage
        initialSearch={initialSearch}
        onSelectSuspect={(id) => navigate(`suspect/${id}`)}
      />
    );
  } else if (routeBase.startsWith('member/')) {
    const memberId = routeBase.replace('member/', '');
    pageContent = (
      <MembersPage
        initialMemberId={memberId}
        onSelectSuspect={(id) => navigate(`suspect/${id}`)}
      />
    );
  } else if (routeBase === 'members') {
    pageContent = (
      <MembersPage
        onSelectSuspect={(id) => navigate(`suspect/${id}`)}
      />
    );
  } else if (routeBase === 'pipeline') {
    pageContent = <PipelineMonitorPage onNavigate={navigate} />;
  } else if (routeBase === 'reviews') {
    pageContent = (
      <ReviewsPage
        onSelectSuspect={(id) => navigate(`suspect/${id}`)}
      />
    );
  } else {
    pageContent = <DashboardPage onNavigate={navigate} />;
  }

  return (
    <div className="min-h-screen bg-background text-on-background flex">
      {/* Sidebar Navigation */}
      <Sidebar currentRoute={routeBase} onNavigate={navigate} />

      {/* Main Workspace Area */}
      <div className="pl-72 flex-1 flex flex-col min-w-0">
        <Topbar
          onNavigate={navigate}
          onSearch={(query) => navigate(`suspects?search=${encodeURIComponent(query)}`)}
        />

        <main className="pt-20 px-8 pb-12 flex-1 max-w-[1500px] w-full mx-auto">
          {pageContent}
        </main>
      </div>
    </div>
  );
}
export default App;
