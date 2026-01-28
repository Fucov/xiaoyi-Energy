/**
 * Sidebar Component
 * ==================
 * 
 * Collapsible sidebar for multi-session management
 * Gemini-style design with new chat button and session list
 */

'use client'

import { useState } from 'react'
import { PanelLeftClose, PanelLeft, Plus, Settings } from 'lucide-react'
import { SessionListItem } from './SessionListItem'
import type { SessionMetadata } from '@/lib/types/session'

interface SidebarProps {
    sessions: SessionMetadata[]
    activeSessionId: string | null
    onNewChat: () => void
    onSelectSession: (sessionId: string) => void
    onDeleteSession: (sessionId: string) => void
    onRenameSession: (sessionId: string, newTitle: string) => void
}

export function Sidebar({
    sessions,
    activeSessionId,
    onNewChat,
    onSelectSession,
    onDeleteSession,
    onRenameSession,
}: SidebarProps) {
    const [collapsed, setCollapsed] = useState(false)

    return (
        <>
            {/* Desktop Sidebar */}
            <aside
                className={`hidden md:flex flex-col bg-dark-800/50 border-r border-white/5 transition-all duration-300 ${collapsed ? 'w-16' : 'w-[280px]'
                    }`}
            >
                {/* Top Section - Toggle & New Chat */}
                <div className="h-12 border-b border-white/5 flex items-center justify-between px-2">
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="p-1.5 hover:bg-dark-600 rounded-md transition-colors"
                        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        {collapsed ? (
                            <PanelLeft className="w-4 h-4 text-gray-400" />
                        ) : (
                            <PanelLeftClose className="w-4 h-4 text-gray-400" />
                        )}
                    </button>

                    {!collapsed && (
                        <button
                            onClick={onNewChat}
                            className="flex items-center gap-2 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-md transition-colors text-sm font-medium"
                        >
                            <Plus className="w-4 h-4" />
                            New Chat
                        </button>
                    )}
                </div>

                {/* Middle Section - Session List */}
                <div className="flex-1 overflow-y-auto py-1.5 px-1.5">
                    {!collapsed ? (
                        sessions.length > 0 ? (
                            sessions.map((session) => (
                                <SessionListItem
                                    key={session.session_id}
                                    session={session}
                                    isActive={session.session_id === activeSessionId}
                                    onSelect={() => onSelectSession(session.session_id)}
                                    onDelete={() => onDeleteSession(session.session_id)}
                                    onRename={(newTitle) => onRenameSession(session.session_id, newTitle)}
                                />
                            ))
                        ) : (
                            <div className="text-center text-gray-500 text-sm mt-8 px-4">
                                No conversations yet
                            </div>
                        )
                    ) : (
                        // Collapsed view - show minimal indicators
                        sessions.slice(0, 5).map((session) => (
                            <button
                                key={session.session_id}
                                onClick={() => onSelectSession(session.session_id)}
                                className={`w-full h-8 rounded-md mb-1 transition-colors ${session.session_id === activeSessionId
                                    ? 'bg-violet-600/20 border border-violet-500/30'
                                    : 'hover:bg-dark-600'
                                    }`}
                                title={session.title}
                            >
                                <div className="w-2 h-2 rounded-full bg-gray-400 mx-auto" />
                            </button>
                        ))
                    )}
                </div>

                {/* Bottom Section - Settings */}
                {!collapsed && (
                    <div className="border-t border-white/5 p-2">
                        <button className="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-dark-600 rounded-md transition-colors text-sm text-gray-300">
                            <Settings className="w-4 h-4" />
                            Settings
                        </button>
                    </div>
                )}
            </aside>

            {/* Mobile Drawer - TODO: Implement drawer for mobile */}
        </>
    )
}
