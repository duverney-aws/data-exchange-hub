import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import AppLayout from '@cloudscape-design/components/app-layout';
import SideNavigation, { SideNavigationProps } from '@cloudscape-design/components/side-navigation';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import BreadcrumbGroup from '@cloudscape-design/components/breadcrumb-group';
import { useAuth } from '../context/AuthContext';

const BREADCRUMB_MAP: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/cmos': 'CMO Partners',
  '/cmo-registration': 'CMO Registration',
  '/data-contracts': 'Data Contracts',
  '/data-contracts/create': 'Create Contract',
  '/integration-patterns': 'Integration Patterns',
  '/schema-management': 'Schema Management',
  '/pipelines': 'Pipelines',
  '/nl-query': 'Natural Language Query',
  '/products': 'Products',
  '/connections': 'Connections',
  '/batches': 'Batches',
};

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(true);
  const { user, signOut } = useAuth();

  const merckNavItems: SideNavigationProps.Item[] = [
    { type: 'link', text: 'Dashboard', href: '/dashboard' },
    { type: 'link', text: 'CMO Partners', href: '/cmos' },
    { type: 'link', text: 'Register New CMO', href: '/cmo-registration' },
    { type: 'link', text: 'Products', href: '/products' },
    { type: 'link', text: 'Connections', href: '/connections' },
    { type: 'link', text: 'Data Contracts', href: '/data-contracts' },
    { type: 'link', text: 'Batches', href: '/batches' },
    { type: 'link', text: 'Schema Management', href: '/schema-management' },
    { type: 'link', text: 'Pipelines', href: '/pipelines' },
    { type: 'divider' },
    { type: 'link', text: 'Natural Language Query', href: '/nl-query' },
  ];

  const cmoNavItems: SideNavigationProps.Item[] = [
    { type: 'link', text: 'Dashboard', href: '/dashboard' },
    { type: 'link', text: 'My Connections', href: '/connections' },
    { type: 'link', text: 'My Contracts', href: '/data-contracts' },
    { type: 'link', text: 'Batches', href: '/batches' },
    { type: 'link', text: 'Integration Setup', href: '/integration-patterns' },
    { type: 'link', text: 'Schema Management', href: '/schema-management' },
    { type: 'link', text: 'Pipelines', href: '/pipelines' },
  ];

  const navItems = user?.isMerckAdmin ? merckNavItems : cmoNavItems;

  const isContractDetail = /^\/data-contracts\/(?!create$).+/.test(location.pathname);
  const currentLabel = isContractDetail ? 'Contract Detail' : (BREADCRUMB_MAP[location.pathname] ?? 'Home');

  const roleLabel = user?.isMerckAdmin ? 'Merck Admin' : 'CMO User';

  return (
    <>
      <TopNavigation
        identity={{ href: '/', title: 'Pharma Data Exchange Hub' }}
        utilities={[
          {
            type: "menu-dropdown",
            text: "Resources",
            iconName: "file",
            items: [
              { id: "user-guide", text: "User Guide", href: "/docs/user-guide.html", external: true },
              { id: "api-guide", text: "API Guide", href: "/docs/api-guide.html", external: true },
            ],
            onItemClick: ({ detail }) => {
              if (detail.id === "user-guide") window.open("/docs/user-guide.html", "_blank"); else if (detail.id === "api-guide") window.open("/docs/api-guide.html", "_blank");
            },
          },
          {
            type: 'menu-dropdown',
            text: user?.name ?? 'User',
            description: `${user?.email} · ${roleLabel}`,
            iconName: 'user-profile',
            items: [
              { id: 'signout', text: 'Sign out' },
            ],
            onItemClick: ({ detail }) => {
              if (detail.id === 'signout') signOut();
            },
          },
        ]}
      />
      <AppLayout
        navigation={
          <SideNavigation
            header={{ text: 'Self-Service Portal', href: '/' }}
            activeHref={location.pathname}
            items={navItems}
            onFollow={(event) => {
              event.preventDefault();
              navigate(event.detail.href);
            }}
          />
        }
        navigationOpen={navOpen}
        onNavigationChange={({ detail }) => setNavOpen(detail.open)}
        breadcrumbs={
          <BreadcrumbGroup
            items={
              location.pathname.startsWith('/data-contracts/') ? [
                { text: 'Home', href: '/' },
                { text: 'Data Contracts', href: '/data-contracts' },
                { text: currentLabel, href: location.pathname },
              ] : [
                { text: 'Home', href: '/' },
                { text: currentLabel, href: location.pathname },
              ]
            }
            onFollow={(event) => { event.preventDefault(); navigate(event.detail.href); }}
          />
        }
        content={<Outlet />}
        toolsHide
      />
    </>
  );
}
