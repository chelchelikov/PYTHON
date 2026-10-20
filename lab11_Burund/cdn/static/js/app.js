// Загрузка списка свободных номеров из REST API и вывод карточек.
// Фотографии берутся с CDN по ссылкам, которые возвращает API.
async function loadRooms() {
  const response = await fetch("http://127.0.0.1:5000/rooms/available");
  const rooms = await response.json();
  const container = document.querySelector(".rooms");
  container.innerHTML = rooms.map(room => `
    <div class="room">
      ${room.photos.length ? `<img src="${room.photos[0]}" alt="Номер ${room.number}">` : ""}
      <div class="info">
        <h3>Номер ${room.number} (${room.room_type})</h3>
        <p>Мест: ${room.capacity}, этаж ${room.floor}</p>
        <p class="price">${room.price} ₽ / ночь</p>
      </div>
    </div>`).join("");
}
document.addEventListener("DOMContentLoaded", loadRooms);
