const grid = document.querySelector('#project-grid');
const updated = document.querySelector('#updated');

function renderProject(project) {
  const card = document.createElement('a');
  card.className = 'project-card';
  card.href = project.url;
  card.target = '_blank';
  card.rel = 'noreferrer';
  const tags = (project.topics || []).slice(0, 4).map(tag => `<span class="pill">${tag}</span>`).join('');
  card.innerHTML = `<h3>${project.name}</h3><p>${project.description || 'Engineering project and technical exploration.'}</p><div class="meta"><span class="pill">${project.language || 'Multi-stack'}</span>${tags}</div>`;
  return card;
}

fetch('data/projects.json')
  .then(response => {
    if (!response.ok) throw new Error('Project data unavailable');
    return response.json();
  })
  .then(data => {
    grid.replaceChildren(...data.projects.map(renderProject));
    updated.textContent = `Updated ${new Date(data.generated_at).toLocaleDateString()}`;
  })
  .catch(() => {
    grid.innerHTML = '<article class="project-card"><h3>Projects</h3><p>Visit GitHub to explore the latest repositories and technical work.</p><div class="meta"><span class="pill">github.com/dedipya001</span></div></article>';
  });
