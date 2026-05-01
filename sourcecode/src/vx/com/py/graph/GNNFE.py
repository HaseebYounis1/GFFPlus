
import random


#from vix.py.proximity.Proximity import Proximity

class GNNFE:

    def __init__(self):
        pass

    @staticmethod
    def execute(neighbors, matrix, proxtype):
        # completing the neighborhood
        origaverage = len(neighbors[0]);
        
        GNNFE.completing(neighbors);

        for i in range(10):
            GNNFE.refining(neighbors, origaverage);
            GNNFE.completing(neighbors);

        # making the NNG connected
        nrcomponents = GNNFE.connecting(neighbors, matrix, proxtype);
        print ("nrcomponents", nrcomponents)
    
    @staticmethod
    def completing(neighbors):
        # O(1) membership test per edge instead of O(k) linear scan
        neighbor_sets = [set(k for k, _ in nbrs) for nbrs in neighbors]
        for i in range(len(neighbors)):
            idx = 0
            while idx < len(neighbors[i]):
                j, w1 = neighbors[i][idx]
                if i not in neighbor_sets[j]:
                    neighbors[j].append([i, w1])
                    neighbor_sets[j].add(i)
                    neighbors[i].append([j, w1])
                    neighbor_sets[i].add(j)
                idx += 1

    @staticmethod
    def refining(neighbors, origaverage):
        for i in range(len(neighbors)):
            if len(neighbors[i]) > origaverage:
                aux = []
                for ne in neighbors[i]:
                    aux.append(ne)

                #Util.shuffle(aux)
                random.seed(7)
                random.shuffle(aux) 

                newnei = []
                for j in range(origaverage):
                    newnei.append(aux[j])
                neighbors[i] = newnei;

    @staticmethod
    def connecting(neighbors, matrix, proxtype):
        nrcomponents = 0;
        visited = set();

        while True:
#        while (visited.size() < neighbors.length) {
            # get the next seed
            seed = 0;
            for i in range (len(neighbors)):
                if  not i in visited:
                    seed = i
                    break

            # if there is some visited node, create a new link from the new seed
            # and some visited node
            if len(visited) > 0:
                # Integer node = visited.iterator().next();
                node = next(iter(visited))
                dist = matrix.proximity_row_ij(node, seed, proxtype);

                newNeighbors1 = [];
                for ne in neighbors[node]:
                    newNeighbors1.append(ne)
                newNeighbors1.append([seed, dist])
                neighbors[node] = newNeighbors1;

                newNeighbors2 = []
                for ne in neighbors[seed]:
                    newNeighbors2.append(ne)
                newNeighbors2.append([node, dist])
                neighbors[seed] = newNeighbors2;
            

            # get the patch starting from the seed
            GNNFE.getComponent(neighbors, visited, seed);
            visited = visited.copy()
            nrcomponents += 1
            
            if not len(visited) < len(neighbors):
                break

        return nrcomponents;

    @staticmethod
    def getComponent(neighborhood, visited, seed):
        visited.add(seed);
        tovisit = set();
        for j, w in neighborhood[seed]:
            if not j in visited:
                tovisit.add(j)

        while True:
            nodes = list(tovisit)
            
            for i in range(len(nodes)):
                tovisit.discard(nodes[i]);
                visited.add(nodes[i]);

                for j, w in neighborhood[nodes[i]]:
                    if not j in visited:
                        tovisit.add(j)

            if not len(tovisit) > 0:
                break
