// Constants
const API_ENDPOINT = '/api/compare';
const MIN_TEAMS = 2;
const MAX_TEAMS = 3;

// DOM Elements
const team1Input = document.getElementById('team1-input');
const team2Input = document.getElementById('team2-input');
const team3Input = document.getElementById('team3-input');
const compareBtn = document.getElementById('compare-btn');
const comparisonResults = document.getElementById('comparison-results');


// Event Listeners
compareBtn.addEventListener('click', handleCompare);
team1Input.addEventListener('keypress', handleEnterKey);
team2Input.addEventListener('keypress', handleEnterKey);
team3Input.addEventListener('keypress', handleEnterKey);

function handleEnterKey(e) {
    if (e.key === 'Enter') {
        handleCompare();
    }
}

async function handleCompare() {
    const team1 = team1Input.value.trim();
    const team2 = team2Input.value.trim();
    const team3 = team3Input.value.trim();

    if (!team1 || !team2) {
        alert('Teams 1 and 2 are required');
        return;
    }

    try {
        console.log('Fetching data for teams:', { team1, team2, team3 });
        
        const response = await fetch(`${API_ENDPOINT}?team1=${team1}&team2=${team2}${team3 ? `&team3=${team3}` : ''}`);
        const data = await response.json();
        
        console.log('Received data:', data);

        if (data.error) {
            alert(data.error);
            return;
        }

        updateDisplay(data);
        comparisonResults.classList.remove('hidden');

    } catch (error) {
        console.error('Error comparing teams:', error);
        alert('An error occurred while comparing teams');
    }
}

function updateDisplay(data) {
    updateTeamCards(data);
    updateRawDataTable(data);
    
    // Add a slight delay to ensure DOM is ready
    setTimeout(() => {
        updateAutoPaths(data);
    }, 100);
}

function updateTeamCards(data) {
    console.log('Updating team cards with data:', data);
    
    // Process each team's data
    Object.entries(data).forEach(([teamNumber, teamData], index) => {
        const cardNum = index + 1;
        const cardId = `team${cardNum}-info`;
        const card = document.getElementById(cardId);
        if (!card) {
          return;
        }

        // Show the card
        card.classList.remove('hidden');

        // Update header information
        document.getElementById(`team${cardNum}-header`).textContent = `Team ${teamNumber}`;
        document.getElementById(`team${cardNum}-number-name`).textContent = teamData.nickname;
        document.getElementById(`team${cardNum}-location`).textContent = 
            `${teamData.city}, ${teamData.state_prov}, ${teamData.country}`;

        const stats = teamData.stats || {};

        // Update Auto Period stats
        document.getElementById(`team${cardNum}-auto-purple-classified`).textContent = (stats.avg_auto_purple_classified || 0).toFixed(2);
        document.getElementById(`team${cardNum}-auto-green-classified`).textContent = (stats.avg_auto_green_classified || 0).toFixed(2);
        document.getElementById(`team${cardNum}-auto-purple-overflow`).textContent = (stats.avg_auto_purple_overflow || 0).toFixed(2);
        document.getElementById(`team${cardNum}-auto-green-overflow`).textContent = (stats.avg_auto_green_overflow || 0).toFixed(2);

        // Update Teleop Period stats
        document.getElementById(`team${cardNum}-teleop-purple-classified`).textContent = (stats.avg_teleop_purple_classified || 0).toFixed(2);
        document.getElementById(`team${cardNum}-teleop-green-classified`).textContent = (stats.avg_teleop_green_classified || 0).toFixed(2);
        document.getElementById(`team${cardNum}-teleop-purple-overflow`).textContent = (stats.avg_teleop_purple_overflow || 0).toFixed(2);
        document.getElementById(`team${cardNum}-teleop-green-overflow`).textContent = (stats.avg_teleop_green_overflow || 0).toFixed(2);

        // Update Endgame stats
        document.getElementById(`team${cardNum}-climb-success`).textContent = ((stats.climb_success_rate || 0) * 100).toFixed(1);
        document.getElementById(`team${cardNum}-preferred-climb`).textContent = stats.preferred_climb_type || '-';

        // Update Robot Disabled stats
        const robotDisabled = teamData.stats?.robot_disabled || [];
        const robotDisabledList = Array.isArray(robotDisabled) ? robotDisabled : [robotDisabled];
        const fullDisabled = robotDisabledList.filter(d => d === 'Full').length;
        const partiallyDisabled = robotDisabledList.filter(d => d === 'Partially').length;
        const totalDisabled = fullDisabled + partiallyDisabled;
        
        let disabledText = totalDisabled > 0 
            ? `Full: ${fullDisabled}, Partial: ${partiallyDisabled}` 
            : 'Never disabled';
        document.getElementById(`team${cardNum}-robot-disabled`).textContent = disabledText;
    });

    // Hide team3 card if no third team
    if (Object.keys(data).length < 3) {
        const team3Card = document.getElementById('team3-info');
        if (team3Card) {
          team3Card.classList.add('hidden');
        }
    }
}


function updateRawDataTable(data) {
    const tbody = document.getElementById('raw-data-tbody');
    if (!tbody) {
      return;
    }

    tbody.innerHTML = '';
    
    Object.entries(data).forEach(([teamNumber, teamData]) => {
        teamData.matches?.forEach(match => {
            const row = document.createElement('tr');

            row.innerHTML = `
                <td class="px-3 sm:px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${teamNumber}
                </td>
                <td class="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.alliance || '-'}
                </td>
                <td class="sm:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.match_number || '-'}
                </td>
                <td class="md:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.auto_purple_classified || 0}/${match.auto_green_classified || 0}
                </td>
                <td class="md:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.auto_purple_overflow || 0}/${match.auto_green_overflow || 0}
                </td>
                <td class="md:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.teleop_purple_classified || 0}/${match.teleop_green_classified || 0}
                </td>
                <td class="md:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.teleop_purple_overflow || 0}/${match.teleop_green_overflow || 0}
                </td>
                <td class="md:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.climb_success ? `${match.climb_type || 'Yes'}` : 'No'}
                </td>
                <td class="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.auto_path ? 
                        `<button onclick='showAutoPath(${JSON.stringify(match.auto_path)}, ${JSON.stringify(match.auto_notes || '')}, "${match.device_type || ''}")' class="text-blue-600 hover:text-blue-800">View</button>` 
                        : 'None'}
                </td>
                <td class="lg:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.notes || '-'}
                </td>
                <td class="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${match.scouter_name || '-'}
                </td>
            `;
            tbody.appendChild(row);
        });
    });
}

// Helper function to get team colors
function getTeamColor(index) {
    const colors = ['#2563eb', '#dc2626', '#059669'];
    return colors[index] || colors[0];
}

function showAutoPath(pathData, autoNotes, deviceType) {
    const modal = document.getElementById('autoPathModal');
    const container = document.getElementById('autoPathContainer');
    const notesElement = document.getElementById('modalAutoNotes');
    
    if (!modal || !container) {
      return;
    }
    
    modal.classList.remove('hidden');
    
    // Initialize canvas with background image
    const CanvasField = new Canvas({
        canvas: document.getElementById('modalAutoPathCanvas'),
        container: container,
        backgroundImage: '/static/images/field-2026.wepb', // credits Team Juice 16236: https://www.reddit.com/r/FTC/comments/1nalob0/decode_custom_field_images_meepmeep_compatible/
        maxPanDistance: 1000
    });

    // Load the path data
    if (pathData) {
        try {
            let sanitizedValue = pathData;
            if (typeof pathData === 'string') {
                // Remove any potential HTML entities
                sanitizedValue = pathData.trim()
                    .replace(/&quot;/g, '"')
                    .replace(/&#34;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&amp;/g, '&');
                
                // Convert single quotes to double quotes if needed
                if (sanitizedValue.startsWith("'") && sanitizedValue.endsWith("'")) {
                    sanitizedValue = sanitizedValue.slice(1, -1);
                }
                sanitizedValue = sanitizedValue.replace(/'/g, '"');
                
                // Convert Python boolean values to JSON boolean values
                sanitizedValue = sanitizedValue
                    .replace(/: True/g, ': true')
                    .replace(/: False/g, ': false');
            }

            const parsedData = typeof sanitizedValue === 'string' ? JSON.parse(sanitizedValue) : sanitizedValue;
            if (Array.isArray(parsedData)) {
                CanvasField.drawingHistory = parsedData;
                CanvasField.redrawCanvas();
            }
        } catch (error) {
            console.error('Error loading path data:', error);
        }
    }

    // Set to readonly mode after loading
    CanvasField.setReadonly(true);

    // Update notes
    if (notesElement) {
        notesElement.textContent = autoNotes || 'No notes available';
    }
}

function closeAutoPathModal() {
    const modal = document.getElementById('autoPathModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('autoPathModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeAutoPathModal();
            }
        });
    }
});

function updateAutoPaths(data) {
    // First, ensure the container exists
    const autoPathsContainer = document.getElementById('auto-paths-container');
    if (!autoPathsContainer) {
        console.error('Auto paths container not found');
        return;
    }

    // Create the single container for all auto paths
    autoPathsContainer.innerHTML = `
        <div class="bg-white shadow-lg rounded-lg overflow-hidden mb-8">
            <div class="bg-gray-50 px-6 py-4 border-b border-gray-200">
                <h3 class="text-xl font-semibold">Auto Paths</h3>
                <p class="text-sm text-gray-600">Latest 5 matches per team</p>
            </div>
            <div class="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            </div>
        </div>
    `;

    const gridContainer = autoPathsContainer.querySelector('.grid');

    Object.entries(data).forEach(([teamNumber, teamData], index) => {
        const teamContainer = document.createElement('div');
        
        // Add team header
        teamContainer.innerHTML = `
            <h4 class="text-lg font-semibold mb-2">Team ${teamNumber} - ${teamData.nickname}</h4>
        `;

        // Get auto paths from matches
        const autoPaths = teamData.matches?.map(match => ({
            match_number: match.match_number,
            path: match.auto_path,
            notes: match.auto_notes,
            device_type: match.device_type
        })).filter(path => path.path) || [];
        
        // Sort paths by match number and take latest 5
        const sortedPaths = [...autoPaths]
            .sort((a, b) => b.match_number - a.match_number)
            .slice(0, 5);

        if (sortedPaths.length === 0) {
            teamContainer.innerHTML += `
                <p class="text-gray-500 italic">No auto paths available</p>
            `;
        } else {
            // Create a table for the paths
            const table = document.createElement('table');
            table.className = 'min-w-full divide-y divide-gray-200';
            
            // Add table header
            table.innerHTML = `
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Match</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Path</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                </tbody>
            `;

            // Add paths to table
            const tbody = table.querySelector('tbody');
            sortedPaths.forEach(pathData => {
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                        ${pathData.match_number}
                    </td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">
                        <button onclick='showAutoPath(${JSON.stringify(pathData.path)}, ${JSON.stringify(pathData.notes || '')}, "${pathData.device_type || ''}")' 
                                class="text-blue-600 hover:text-blue-800">
                            View Path
                        </button>
                    </td>
                    <td class="px-3 py-2 text-sm text-gray-500">
                        ${pathData.notes || '-'}
                    </td>
                `;
                
                tbody.appendChild(row);
            });
            
            teamContainer.appendChild(table);
        }

        gridContainer.appendChild(teamContainer);
    });
}