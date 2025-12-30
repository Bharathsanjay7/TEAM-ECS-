import { useState, useEffect } from 'react';
import { GloveMonitor } from './components/GloveMonitor';
import { GestureRecognition } from './components/GestureRecognition';
import { SpeechOutput } from './components/SpeechOutput';
import { CaregiverAlerts } from './components/CaregiverAlerts';
import { Settings } from './components/Settings';
import { Hand, Mic, Bell, Settings as SettingsIcon, Activity } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('monitor');
  const [language, setLanguage] = useState('en');
  const [isConnected, setIsConnected] = useState(true);
  const [currentGesture, setCurrentGesture] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);

  const tabs = [
    { id: 'monitor', label: 'Glove Monitor', icon: Hand },
    { id: 'gestures', label: 'Gestures', icon: Activity },
    { id: 'speech', label: 'Speech', icon: Mic },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
  ];

  const handleEmergencyAlert = (gesture: string) => {
    const newAlert = {
      id: Date.now(),
      gesture,
      timestamp: new Date(),
      type: 'emergency',
    };
    setAlerts(prev => [newAlert, ...prev]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-indigo-900 mb-2">IoT Sign-to-Speech Glove</h1>
              <p className="text-gray-600">Bridging communication gaps with smart gesture recognition</p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${isConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                <span className="text-sm font-medium">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bg-white rounded-2xl shadow-lg mb-6 overflow-hidden">
          <div className="flex overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-6 py-4 whitespace-nowrap transition-all ${
                    activeTab === tab.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{tab.label}</span>
                  {tab.id === 'alerts' && alerts.length > 0 && (
                    <span className="bg-red-500 text-white text-xs px-2 py-1 rounded-full">
                      {alerts.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content Area */}
        <div className="bg-white rounded-2xl shadow-lg p-6">
          {activeTab === 'monitor' && (
            <GloveMonitor 
              isConnected={isConnected} 
              currentGesture={currentGesture}
              setCurrentGesture={setCurrentGesture}
              onEmergencyAlert={handleEmergencyAlert}
            />
          )}
          {activeTab === 'gestures' && (
            <GestureRecognition 
              language={language}
              onGestureDetected={setCurrentGesture}
              onEmergencyAlert={handleEmergencyAlert}
            />
          )}
          {activeTab === 'speech' && (
            <SpeechOutput 
              currentGesture={currentGesture} 
              language={language}
            />
          )}
          {activeTab === 'alerts' && (
            <CaregiverAlerts alerts={alerts} setAlerts={setAlerts} />
          )}
          {activeTab === 'settings' && (
            <Settings 
              language={language} 
              setLanguage={setLanguage}
              isConnected={isConnected}
              setIsConnected={setIsConnected}
            />
          )}
        </div>
      </div>
    </div>
  );
}
